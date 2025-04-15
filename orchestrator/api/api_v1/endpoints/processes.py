# Copyright 2019-2025 SURF, GÉANT, ESnet.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module that implements process related API endpoints."""

import struct
import zlib
from http import HTTPStatus
from typing import Any
from uuid import UUID

import structlog
from fastapi import Request
from fastapi.param_functions import Body, Depends, Header
from fastapi.routing import APIRouter
from fastapi.websockets import WebSocket
from fastapi_etag.dependency import CacheHit
from more_itertools import chunked
from sentry_sdk.tracing import trace
from sqlalchemy import CompoundSelect, Select, select
from sqlalchemy.orm import defer, joinedload
from sqlalchemy.sql.functions import count
from starlette.responses import Response

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import add_response_range
from orchestrator.db import ProcessSubscriptionTable, ProcessTable, SubscriptionTable, db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.process import filter_processes
from orchestrator.db.sorting import Sort, SortOrder
from orchestrator.db.sorting.process import sort_processes
from orchestrator.schemas import ProcessIdSchema, ProcessResumeAllSchema, ProcessSchema, ProcessStatusCounts, Reporter
from orchestrator.security import authenticate
from orchestrator.services.process_broadcast_thread import api_broadcast_process_data
from orchestrator.services.processes import (
    SYSTEM_USER,
    _async_resume_processes,
    _get_process,
    abort_process,
    continue_awaiting_process,
    load_process,
    resume_process,
    start_process,
    update_awaiting_process_progress,
)
from orchestrator.services.settings import get_engine_settings
from orchestrator.settings import app_settings
from orchestrator.utils.enrich_process import enrich_process
from orchestrator.websocket import (
    WS_CHANNELS,
    broadcast_invalidate_status_counts,
    broadcast_process_update_to_websocket,
    websocket_manager,
)
from orchestrator.workflow import ProcessStatus
from pydantic_forms.types import JSON, State

router = APIRouter()

logger = structlog.get_logger(__name__)


def check_global_lock() -> None:
    """Check the global lock of the engine.

    Returns:
        None or raises an exception

    """
    engine_settings = get_engine_settings()
    if engine_settings.global_lock:
        logger.info("Unable to interact with processes at this time. Engine StatusEnum is locked")
        raise_status(
            HTTPStatus.SERVICE_UNAVAILABLE, detail="Engine is locked cannot accept changes on processes at this time"
        )


def resolve_user_name(
    *,
    reporter: Reporter | None,
    resolved_user: OIDCUserModel | None,
) -> str:
    if reporter:
        return reporter

    if resolved_user:
        return resolved_user.name if resolved_user.name else resolved_user.user_name

    return SYSTEM_USER


def user_name(
    reporter: Reporter | None = None,
    user: OIDCUserModel | None = Depends(authenticate),
) -> str:
    return resolve_user_name(reporter=reporter, resolved_user=user)


@router.delete("/{process_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete(process_id: UUID) -> None:
    stmt = select(ProcessTable).filter_by(process_id=process_id)
    process = db.session.execute(stmt).scalar_one_or_none()

    if not process:
        raise_status(HTTPStatus.NOT_FOUND)

    db.session.delete(db.session.get(ProcessTable, process_id))
    db.session.commit()

    broadcast_invalidate_status_counts()
    broadcast_process_update_to_websocket(process.process_id)


@router.post(
    "/{workflow_key}",
    response_model=ProcessIdSchema,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(check_global_lock, use_cache=False)],
)
def new_process(
    workflow_key: str,
    request: Request,
    json_data: list[dict[str, Any]] | None = Body(...),
    user: str = Depends(user_name),
    user_model: OIDCUserModel | None = Depends(authenticate),
) -> dict[str, UUID]:
    broadcast_func = api_broadcast_process_data(request)
    process_id = start_process(
        workflow_key, user_inputs=json_data, user_model=user_model, user=user, broadcast_func=broadcast_func
    )

    return {"id": process_id}


@router.put(
    "/{process_id}/resume",
    response_model=None,
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[Depends(check_global_lock, use_cache=False)],
)
def resume_process_endpoint(
    process_id: UUID, request: Request, json_data: JSON = Body(...), user: str = Depends(user_name)
) -> None:
    process = _get_process(process_id)

    if process.last_status == ProcessStatus.COMPLETED:
        raise_status(HTTPStatus.CONFLICT, "Resuming a completed workflow is not possible")

    if process.last_status == ProcessStatus.RUNNING:
        raise_status(HTTPStatus.CONFLICT, "Resuming a running workflow is not possible")

    if process.last_status == ProcessStatus.RESUMED:
        raise_status(HTTPStatus.CONFLICT, "Resuming a resumed workflow is not possible")

    broadcast_invalidate_status_counts()
    broadcast_func = api_broadcast_process_data(request)

    resume_process(process, user=user, user_inputs=json_data, broadcast_func=broadcast_func)


@router.post(
    "/{process_id}/callback/{token}",
    response_model=None,
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_global_lock, use_cache=False)],
)
def continue_awaiting_process_endpoint(
    process_id: UUID,
    token: str,
    request: Request,
    json_data: State = Body(...),
) -> None:
    check_global_lock()

    process = _get_process(process_id)

    if process.last_status != ProcessStatus.AWAITING_CALLBACK:
        raise_status(HTTPStatus.CONFLICT, "This process is not in an awaiting state.")

    try:
        broadcast_func = api_broadcast_process_data(request)
        continue_awaiting_process(process, token=token, input_data=json_data, broadcast_func=broadcast_func)
    except AssertionError as e:
        raise_status(HTTPStatus.NOT_FOUND, str(e))


@router.post(
    "/{process_id}/callback/{token}/progress",
    response_model=None,
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_global_lock, use_cache=False)],
)
def update_progress_on_awaiting_process_endpoint(
    process_id: UUID,
    token: str,
    data: str | State = Body(...),
) -> None:
    process = _get_process(process_id)

    if process.last_status != ProcessStatus.AWAITING_CALLBACK:
        raise_status(HTTPStatus.CONFLICT, "This process is not in an awaiting state.")

    try:
        update_awaiting_process_progress(process, token=token, data=data)
    except AssertionError as exc:
        raise_status(HTTPStatus.NOT_FOUND, str(exc))


@router.put(
    "/resume-all", response_model=ProcessResumeAllSchema, dependencies=[Depends(check_global_lock, use_cache=False)]
)
async def resume_all_processess_endpoint(request: Request, user: str = Depends(user_name)) -> dict[str, int]:
    """Retry all task processes in status Failed, Waiting, API Unavailable or Inconsistent Data.

    The retry is started in the background, returning status 200 and number of processes in message.
    When it is already running, refuse and return status 409 instead.
    """

    # Retrieve processes eligible for resuming
    stmt = (
        select(ProcessTable)
        .filter(
            ProcessTable.last_status.in_(
                [
                    ProcessStatus.FAILED,
                    ProcessStatus.WAITING,
                    ProcessStatus.API_UNAVAILABLE,
                    ProcessStatus.INCONSISTENT_DATA,
                ]
            )
        )
        .filter(ProcessTable.is_task.is_(True))
    )
    processes_to_resume = db.session.scalars(stmt).all()

    broadcast_func = api_broadcast_process_data(request)
    if not await _async_resume_processes(processes_to_resume, user, broadcast_func=broadcast_func):
        raise_status(HTTPStatus.CONFLICT, "Another request to resume all processes is in progress")

    logger.info("Resuming all processes", count=len(processes_to_resume))

    return {"count": len(processes_to_resume)}


@router.put("/{process_id}/abort", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def abort_process_endpoint(process_id: UUID, request: Request, user: str = Depends(user_name)) -> None:
    process = _get_process(process_id)

    broadcast_func = api_broadcast_process_data(request)
    try:
        abort_process(process, user, broadcast_func=broadcast_func)
        broadcast_invalidate_status_counts()
        return
    except Exception as e:
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


@router.get("/status-counts", response_model=ProcessStatusCounts)
def status_counts() -> ProcessStatusCounts:
    """Retrieve status counts for processes and tasks."""

    stmt = (
        select(ProcessTable)
        .with_only_columns(ProcessTable.is_task, ProcessTable.last_status, count(ProcessTable.last_status))
        .group_by(ProcessTable.is_task, ProcessTable.last_status)
    )
    rows = db.session.execute(stmt).all()
    return ProcessStatusCounts(
        process_counts={status: num_processes for is_task, status, num_processes in rows if not is_task},
        task_counts={status: num_processes for is_task, status, num_processes in rows if is_task},
    )


@router.get("/{process_id}", response_model=ProcessSchema)
def show(process_id: UUID) -> dict[str, Any]:
    process = _get_process(process_id)
    p = load_process(process)

    return enrich_process(process, p)


def handle_process_error(message: str, **kwargs: Any) -> None:
    logger.debug(message, **kwargs)
    raise_status(HTTPStatus.BAD_REQUEST, message)


@trace
def _calculate_processes_crc32_checksum(results: list[ProcessTable]) -> int:
    """Calculate a CRC32 checksum of all the process id's and last_modified_at dates in order."""
    checksum = 0
    for p in results:
        checksum = zlib.crc32(p.process_id.bytes, checksum)
        last_modified_as_bytes = struct.pack("d", p.last_modified_at.timestamp())
        checksum = zlib.crc32(last_modified_as_bytes, checksum)
    return checksum


@router.get("/", response_model=list[ProcessSchema])
def processes_filterable(  # noqa: C901
    response: Response,
    range: str | None = None,
    sort: str | None = None,
    filter: str | None = None,
    if_none_match: str | None = Header(None),
) -> list[dict[str, Any]]:
    _range: list[int] | None = list(map(int, range.split(","))) if range else None
    _sort: list[str] | None = sort.split(",") if sort else None
    _filter: list[str] | None = filter.split(",") if filter else None

    # the joinedload on ProcessSubscriptionTable.subscription via ProcessBaseSchema.process_subscriptions prevents a query for every subscription later.
    # tracebacks are not presented in the list of processes and can be really large.
    processes: Select | CompoundSelect
    processes = select(ProcessTable).options(
        joinedload(ProcessTable.process_subscriptions)
        .joinedload(ProcessSubscriptionTable.subscription)
        .joinedload(SubscriptionTable.product),
        defer(ProcessTable.traceback),
    )

    if _filter is not None:
        if len(_filter) == 0 or (len(_filter) % 2) > 0:
            raise_status(HTTPStatus.BAD_REQUEST, "Invalid number of filter arguments")

        pydantic_filters = [Filter(field=field, value=value) for field, value in chunked(_filter, 2)]
        processes = filter_processes(processes, pydantic_filters, handle_process_error)

    if _sort is not None and len(_sort) >= 2:
        pydantic_sorting = [Sort(field=field, order=SortOrder[value.upper()]) for field, value in chunked(_sort, 2)]
        processes = sort_processes(processes, pydantic_sorting, handle_process_error)

    processes = add_response_range(processes, _range, response, unit="processes")

    results = list(db.session.scalars(processes).unique())

    # Calculate a CRC32 checksum of all the process id's and last_modified_at dates in order as entity tag
    checksum = _calculate_processes_crc32_checksum(results)

    entity_tag = hex(checksum)
    response.headers["ETag"] = f'W/"{entity_tag}"'

    # When the If-None-Match header contains the same CRC we can be sure that the resource has not changed,
    # so we can skip serialization at the backend and rerendering at the frontend.
    if if_none_match == entity_tag:
        raise CacheHit(HTTPStatus.NOT_MODIFIED, headers=dict(response.headers))

    return [enrich_process(p) for p in results]


ws_router = APIRouter()

if app_settings.ENABLE_WEBSOCKETS:

    @ws_router.websocket("/all/")
    async def websocket_process_list(websocket: WebSocket, token: str) -> None:
        error = await websocket_manager.authorize(websocket, token)

        await websocket.accept()
        if error:
            await websocket_manager.disconnect(websocket, reason=error)
            return

        channel = WS_CHANNELS.ALL_PROCESSES
        await websocket_manager.connect(websocket, channel)

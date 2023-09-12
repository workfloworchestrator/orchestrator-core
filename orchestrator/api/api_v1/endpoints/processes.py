# Copyright 2019-2020 SURF.
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
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import structlog
from deprecated import deprecated
from fastapi import Request
from fastapi.param_functions import Body, Depends, Header
from fastapi.routing import APIRouter
from fastapi.websockets import WebSocket
from fastapi_etag.dependency import CacheHit
from more_itertools import chunked
from sentry_sdk.tracing import trace
from sqlalchemy.orm import contains_eager, defer, joinedload
from sqlalchemy.sql.functions import count
from starlette.responses import Response

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.error_handling import raise_status
from orchestrator.config.assignee import Assignee
from orchestrator.db import EngineSettingsTable, ProcessSubscriptionTable, ProcessTable, SubscriptionTable, db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.process import filter_processes
from orchestrator.db.sorting import Sort, SortOrder
from orchestrator.db.sorting.process import sort_processes
from orchestrator.schemas import (
    ProcessDeprecationsSchema,
    ProcessIdSchema,
    ProcessResumeAllSchema,
    ProcessSubscriptionBaseSchema,
    ProcessSubscriptionSchema,
)
from orchestrator.schemas.process import ProcessStatusCounts
from orchestrator.security import oidc_user
from orchestrator.services.processes import (
    SYSTEM_USER,
    _async_resume_processes,
    _get_process,
    abort_process,
    api_broadcast_process_data,
    load_process,
    resume_process,
    start_process,
)
from orchestrator.settings import app_settings
from orchestrator.types import JSON
from orchestrator.utils.enrich_process import enrich_process
from orchestrator.websocket import WS_CHANNELS, send_process_data_to_websocket, websocket_manager
from orchestrator.workflow import ProcessStatus

router = APIRouter()

logger = structlog.get_logger(__name__)


@router.delete("/{process_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete(process_id: UUID) -> None:
    process = ProcessTable.query.filter_by(process_id=process_id).one_or_none()
    if not process:
        raise_status(HTTPStatus.NOT_FOUND)

    websocket_data = {"process": {"id": process.process_id, "status": ProcessStatus.ABORTED}}
    send_process_data_to_websocket(process.process_id, websocket_data)

    ProcessTable.query.filter_by(process_id=process_id).delete()
    db.session.commit()


@router.post("/{workflow_key}", response_model=ProcessIdSchema, status_code=HTTPStatus.CREATED)
def new_process(
    workflow_key: str,
    request: Request,
    json_data: Optional[List[Dict[str, Any]]] = Body(...),
    user: Optional[OIDCUserModel] = Depends(oidc_user),
) -> Dict[str, UUID]:
    check_global_lock()

    user_name = user.user_name if user else SYSTEM_USER
    broadcast_func = api_broadcast_process_data(request)
    process_id = start_process(workflow_key, user_inputs=json_data, user=user_name, broadcast_func=broadcast_func)

    return {"id": process_id}


@router.put("/{process_id}/resume", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def resume_process_endpoint(
    process_id: UUID, request: Request, json_data: JSON = Body(...), user: Optional[OIDCUserModel] = Depends(oidc_user)
) -> None:
    check_global_lock()

    process = _get_process(process_id)

    if process.last_status == ProcessStatus.COMPLETED:
        raise_status(HTTPStatus.CONFLICT, "Resuming a completed workflow is not possible")

    if process.last_status == ProcessStatus.RUNNING:
        raise_status(HTTPStatus.CONFLICT, "Resuming a running workflow is not possible")

    if process.last_status == ProcessStatus.RESUMED:
        raise_status(HTTPStatus.CONFLICT, "Resuming a resumed workflow is not possible")

    user_name = user.user_name if user else SYSTEM_USER

    broadcast_func = api_broadcast_process_data(request)
    resume_process(process, user=user_name, user_inputs=json_data, broadcast_func=broadcast_func)


@router.put("/resume-all", response_model=ProcessResumeAllSchema)
async def resume_all_processess_endpoint(
    request: Request, user: Optional[OIDCUserModel] = Depends(oidc_user)
) -> Dict[str, int]:
    """Retry all task processes in status Failed, Waiting, API Unavailable or Inconsistent Data.

    The retry is started in the background, returning status 200 and number of processes in message.
    When it is already running, refuse and return status 409 instead.
    """
    check_global_lock()

    user_name = user.user_name if user else SYSTEM_USER

    # Retrieve processes eligible for resuming
    processes_to_resume = (
        ProcessTable.query.filter(
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
        .all()
    )

    broadcast_func = api_broadcast_process_data(request)
    if not await _async_resume_processes(processes_to_resume, user_name, broadcast_func=broadcast_func):
        raise_status(HTTPStatus.CONFLICT, "Another request to resume all processes is in progress")

    logger.info("Resuming all processes", count=len(processes_to_resume))

    return {"count": len(processes_to_resume)}


@router.put("/{process_id}/abort", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def abort_process_endpoint(
    process_id: UUID, request: Request, user: Optional[OIDCUserModel] = Depends(oidc_user)
) -> None:
    process = _get_process(process_id)

    user_name = user.user_name if user else SYSTEM_USER
    broadcast_func = api_broadcast_process_data(request)
    try:
        abort_process(process, user_name, broadcast_func=broadcast_func)
        return
    except Exception as e:
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


@router.get(
    "/process-subscriptions-by-subscription-id/{subscription_id}", response_model=List[ProcessSubscriptionSchema]
)
def process_subscriptions_by_subscription_id(subscription_id: UUID) -> List[ProcessSubscriptionSchema]:
    query = (
        ProcessSubscriptionTable.query.options(contains_eager(ProcessSubscriptionTable.process))
        .join(ProcessTable)
        .filter(ProcessSubscriptionTable.subscription_id == subscription_id)
        .order_by(ProcessTable.started_at.asc())
    )
    return query.all()


@deprecated("Changed to '/process-subscriptions-by-process_id/{process_id}' from version 1.2.3, will be removed in 1.4")
@router.get("/process-subscriptions-by-pid/{pid}", response_model=List[ProcessSubscriptionBaseSchema])
def process_subscriptions_by_process_pid(pid: UUID) -> List[ProcessSubscriptionTable]:
    return ProcessSubscriptionTable.query.filter_by(process_id=pid).all()


@router.get("/process-subscriptions-by-process_id/{process_id}", response_model=List[ProcessSubscriptionBaseSchema])
def process_subscriptions_by_process_process_id(process_id: UUID) -> List[ProcessSubscriptionTable]:
    return ProcessSubscriptionTable.query.filter_by(process_id=process_id).all()


def check_global_lock() -> None:
    """Check the global lock of the engine.

    Returns:
        None or raises an exception

    """
    engine_settings = EngineSettingsTable.query.one()
    if engine_settings.global_lock:
        logger.info("Unable to interact with processes at this time. Engine StatusEnum is locked")
        raise_status(
            HTTPStatus.SERVICE_UNAVAILABLE, detail="Engine is locked cannot accept changes on processes at this time"
        )


@router.get("/statuses", response_model=List[ProcessStatus])
def statuses() -> List[str]:
    return [status.value for status in ProcessStatus]


@router.get("/status-counts", response_model=ProcessStatusCounts)
def status_counts() -> ProcessStatusCounts:
    """Retrieve status counts for processes and tasks."""
    rows = (
        ProcessTable.query.with_entities(
            ProcessTable.is_task, ProcessTable.last_status, count(ProcessTable.last_status)
        )
        .group_by(ProcessTable.is_task, ProcessTable.last_status)
        .all()
    )
    return ProcessStatusCounts(
        process_counts={status: num_processes for is_task, status, num_processes in rows if not is_task},
        task_counts={status: num_processes for is_task, status, num_processes in rows if is_task},
    )


@router.get("/assignees", response_model=List[Assignee])
def assignees() -> List[str]:
    return [assignee.value for assignee in Assignee]


@deprecated("product (UUID) changed to product_id from version 1.2.3, will be removed in 1.4")
def convert_to_old_process(process: dict) -> dict:
    return {**process, "product": process["product_id"]}


@router.get("/{process_id}", response_model=ProcessDeprecationsSchema)
def show(process_id: UUID) -> Dict[str, Any]:
    process = _get_process(process_id)
    p = load_process(process)

    return convert_to_old_process(enrich_process(process, p))


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


@router.get("/", response_model=List[ProcessDeprecationsSchema])
def processes_filterable(  # noqa: C901
    response: Response,
    range: Optional[str] = None,
    sort: Optional[str] = None,
    filter: Optional[str] = None,
    if_none_match: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    _range: Union[List[int], None] = list(map(int, range.split(","))) if range else None
    _sort: Union[List[str], None] = sort.split(",") if sort else None
    _filter: Union[List[str], None] = filter.split(",") if filter else None

    # the joinedload on ProcessSubscriptionTable.subscription via ProcessBaseSchema.process_subscriptions prevents a query for every subscription later.
    # tracebacks are not presented in the list of processes and can be really large.
    query = ProcessTable.query.options(
        joinedload(ProcessTable.process_subscriptions)
        .joinedload(ProcessSubscriptionTable.subscription)
        .joinedload(SubscriptionTable.product),
        defer("traceback"),
    )

    if _filter is not None:
        if len(_filter) == 0 or (len(_filter) % 2) > 0:
            raise_status(HTTPStatus.BAD_REQUEST, "Invalid number of filter arguments")

        pydantic_filters = [Filter(field=field, value=value) for field, value in chunked(_filter, 2)]
        query = filter_processes(query, pydantic_filters, handle_process_error)

    if _sort is not None and len(_sort) >= 2:
        pydantic_sorting = [Sort(field=field, order=SortOrder[value.upper()]) for field, value in chunked(_sort, 2)]
        query = sort_processes(query, pydantic_sorting, handle_process_error)

    if _range is not None and len(_range) == 2:
        try:
            range_start = int(_range[0])
            range_end = int(_range[1])
            if range_start >= range_end:
                raise ValueError("range start must be lower than end")
        except (ValueError, AssertionError):
            msg = "Invalid range parameters"
            logger.exception(msg)
            raise_status(HTTPStatus.BAD_REQUEST, msg)
        total = query.count()
        query = query.slice(range_start, range_end)

        response.headers["Content-Range"] = f"processes {range_start}-{range_end}/{total}"

    results = query.all()

    # Calculate a CRC32 checksum of all the process id's and last_modified_at dates in order as entity tag
    checksum = _calculate_processes_crc32_checksum(results)

    entity_tag = hex(checksum)
    response.headers["ETag"] = f'W/"{entity_tag}"'

    # When the If-None-Match header contains the same CRC we can be sure that the resource has not changed
    # so we can skip serialization at the backend and rerendering at the frontend.
    if if_none_match == entity_tag:
        raise CacheHit(HTTPStatus.NOT_MODIFIED, headers=dict(response.headers))

    return [convert_to_old_process(enrich_process(p)) for p in results]


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

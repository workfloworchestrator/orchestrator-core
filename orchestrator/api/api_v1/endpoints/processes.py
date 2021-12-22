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
from dataclasses import asdict
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import structlog
from fastapi import Query, WebSocket
from fastapi.param_functions import Body, Depends, Header
from fastapi.routing import APIRouter
from fastapi_etag.dependency import CacheHit
from more_itertools import chunked
from oauth2_lib.fastapi import OIDCUserModel
from sqlalchemy import String, cast
from sqlalchemy.orm import contains_eager, defer, joinedload
from sqlalchemy.sql import expression
from starlette.responses import Response

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import VALID_SORT_KEYS, enrich_process
from orchestrator.config.assignee import Assignee
from orchestrator.db import (
    EngineSettingsTable,
    ProcessSubscriptionTable,
    ProcessTable,
    ProductTable,
    SubscriptionTable,
    db,
)
from orchestrator.schemas import (
    ProcessIdSchema,
    ProcessListItemSchema,
    ProcessSchema,
    ProcessSubscriptionBaseSchema,
    ProcessSubscriptionSchema,
)
from orchestrator.security import oidc_user
from orchestrator.services.processes import SYSTEM_USER, abort_process, load_process, resume_process, start_process
from orchestrator.types import JSON
from orchestrator.utils.show_process import show_process
from orchestrator.websocket import WS_CHANNELS, websocket_enabled, websocket_manager
from orchestrator.workflow import ProcessStatus

router = APIRouter()

logger = structlog.get_logger(__name__)


def _get_process(pid: UUID) -> ProcessTable:
    process = ProcessTable.query.options(
        joinedload(ProcessTable.steps),
        joinedload(ProcessTable.process_subscriptions).joinedload(ProcessSubscriptionTable.subscription),
    ).get(pid)

    if not process:
        raise_status(HTTPStatus.NOT_FOUND, f"Process with pid {pid} not found")

    return process


@router.delete("/{pid}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete(pid: UUID) -> None:
    count = ProcessTable.query.filter_by(pid=pid).delete()
    db.session.commit()
    if count > 0:
        return None
    else:
        raise_status(HTTPStatus.NOT_FOUND)


@router.post("/{workflow_key}", response_model=ProcessIdSchema, status_code=HTTPStatus.CREATED)
def new_process(
    workflow_key: str,
    json_data: Optional[List[Dict[str, Any]]] = Body(...),
    user: Optional[OIDCUserModel] = Depends(oidc_user),
) -> Dict[str, UUID]:
    check_global_lock()

    user_name = user.user_name if user else SYSTEM_USER
    pid = start_process(workflow_key, user_inputs=json_data, user=user_name)[0]

    return {"id": pid}


@router.put("/{pid}/resume", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def resume_process_endpoint(
    pid: UUID, json_data: JSON = Body(...), user: Optional[OIDCUserModel] = Depends(oidc_user)
) -> None:
    check_global_lock()

    process = _get_process(pid)

    if process.last_status == ProcessStatus.RUNNING:
        raise_status(HTTPStatus.CONFLICT, "Resuming a running workflow is not possible")

    user_name = user.user_name if user else SYSTEM_USER

    resume_process(process, user=user_name, user_inputs=json_data)


@router.put("/{pid}/abort", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def abort_process_endpoint(pid: UUID, user: Optional[OIDCUserModel] = Depends(oidc_user)) -> None:
    process = _get_process(pid)

    user_name = user.user_name if user else SYSTEM_USER

    try:
        abort_process(process, user_name)
        return None
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


@router.get("/process-subscriptions-by-pid/{pid}", response_model=List[ProcessSubscriptionBaseSchema])
def process_subscriptions_by_process_pid(pid: UUID) -> List[ProcessSubscriptionTable]:
    return ProcessSubscriptionTable.query.filter_by(pid=pid).all()


def check_global_lock() -> None:
    """
    Check the global lock of the engine.

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


@router.get("/assignees", response_model=List[Assignee])
def assignees() -> List[str]:
    return [assignee.value for assignee in Assignee]


@router.get("/{pid}", response_model=ProcessSchema)
def show(pid: UUID) -> Dict[str, Any]:
    process = _get_process(pid)
    p = load_process(process)

    data = show_process(process, p)
    return data


@router.get("/", response_model=List[ProcessListItemSchema])
def processes_filterable(
    response: Response,
    range: Optional[str] = None,
    sort: Optional[str] = None,
    filter: Optional[str] = None,
    if_none_match: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    _range: Union[List[int], None] = list(map(int, range.split(","))) if range else None
    _sort: Union[List[str], None] = sort.split(",") if sort else None
    _filter: Union[List[str], None] = filter.split(",") if filter else None
    logger.info("processes_filterable() called", range=_range, sort=_sort, filter=_filter)

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
        for filter_pair in chunked(_filter, 2):
            field, value = filter_pair
            field = field.lower()
            if value is not None:
                if field == "istask":
                    value_as_bool = value.lower() in ("yes", "y", "ye", "true", "1", "ja")
                    query = query.filter(ProcessTable.is_task.is_(value_as_bool))
                elif field == "assignee":
                    assignees = value.split("-")
                    query = query.filter(ProcessTable.assignee.in_(assignees))
                elif field == "status":
                    statuses = value.split("-")
                    query = query.filter(ProcessTable.last_status.in_(statuses))
                elif field == "workflow":
                    query = query.filter(ProcessTable.workflow.ilike("%" + value + "%"))
                elif field == "creator":
                    query = query.filter(ProcessTable.created_by.ilike("%" + value + "%"))
                elif field == "organisation":
                    try:
                        value_as_uuid = UUID(value)
                    except (ValueError, AttributeError):
                        msg = "Not a valid customer_id, must be a UUID: '{value}'"
                        logger.exception(msg)
                        raise_status(HTTPStatus.BAD_REQUEST, msg)
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable)
                        .filter(SubscriptionTable.customer_id == value_as_uuid)
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "product":
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable, ProductTable)
                        .filter(ProductTable.name.ilike("%" + value + "%"))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "tag":
                    tags = value.split("-")
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable, ProductTable)
                        .filter(ProductTable.tag.in_(tags))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "subscriptions":
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable)
                        .filter(SubscriptionTable.description.ilike("%" + value + "%"))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "pid":
                    query = query.filter(cast(ProcessTable.pid, String).ilike("%" + value + "%"))
                elif field == "target":
                    targets = value.split("-")
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .filter(ProcessSubscriptionTable.workflow_target.in_(targets))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                else:
                    raise_status(HTTPStatus.BAD_REQUEST, f"Invalid filter '{field}'")

    if _sort is not None and len(_sort) >= 2:
        for _sort in chunked(_sort, 2):
            if _sort and len(_sort) == 2 and _sort[0] in VALID_SORT_KEYS:
                sort_key = VALID_SORT_KEYS[_sort[0]]
                if _sort[1].upper() == "DESC":
                    query = query.order_by(expression.desc(ProcessTable.__dict__[sort_key]))
                else:
                    query = query.order_by(expression.asc(ProcessTable.__dict__[sort_key]))
            else:
                raise_status(HTTPStatus.BAD_REQUEST, "Invalid Sort parameters")

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
    checksum = 0
    for p in results:
        checksum = zlib.crc32(p.pid.bytes, checksum)
        last_modified_as_bytes = struct.pack("d", p.last_modified_at.timestamp())
        checksum = zlib.crc32(last_modified_as_bytes, checksum)

    entity_tag = hex(checksum)
    response.headers["ETag"] = f'W/"{entity_tag}"'

    # When the If-None-Match header contains the same CRC we can be sure that the resource has not changed
    # so we can skip serialization at the backend and rerendering at the frontend.
    if if_none_match == entity_tag:
        raise CacheHit(HTTPStatus.NOT_MODIFIED, headers=dict(response.headers))

    return [asdict(enrich_process(p)) for p in results]


@router.websocket("/all/")
@websocket_enabled
async def websocket_process_list(websocket: WebSocket, token: str = Query(...)) -> None:
    error = await websocket_manager.authorize(websocket, token)

    await websocket.accept()
    if error:
        await websocket_manager.disconnect(websocket, reason=error)
        return

    channel = WS_CHANNELS.ALL_PROCESSES
    await websocket_manager.connect(websocket, channel)

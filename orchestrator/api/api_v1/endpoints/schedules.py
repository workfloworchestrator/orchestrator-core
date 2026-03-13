# Copyright 2019-2025 SURF.
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
from http import HTTPStatus

import structlog
from fastapi import Depends
from fastapi.routing import APIRouter
from more_itertools import first

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.error_handling import raise_status
from orchestrator.schedules.service import add_scheduled_task_to_queue, get_linker_entries_by_schedule_ids
from orchestrator.schemas.schedules import APSchedulerJobCreate, APSchedulerJobDelete, APSchedulerJobUpdate
from orchestrator.security import authenticate
from orchestrator.services.workflows import get_workflow_by_workflow_id
from orchestrator.workflows import get_workflow

logger = structlog.get_logger(__name__)

router: APIRouter = APIRouter()


@router.post("/", status_code=HTTPStatus.CREATED)
async def create_scheduled_task(
    payload: APSchedulerJobCreate, user_model: OIDCUserModel | None = Depends(authenticate)
) -> dict[str, str]:
    """Create a scheduled task."""
    task_key = payload.workflow_name
    task = get_workflow(payload.workflow_name)

    if not task:
        raise_status(HTTPStatus.NOT_FOUND, "Task does not exist")
    if not await task.authorize_callback(user_model):
        raise_status(HTTPStatus.FORBIDDEN, f"User is not authorized to create schedule with '{task_key}' task")

    add_scheduled_task_to_queue(payload)
    return {"message": "Added to Create Queue", "status": "CREATED"}


@router.put("/", status_code=HTTPStatus.OK)
async def update_scheduled_task(
    payload: APSchedulerJobUpdate, user_model: OIDCUserModel | None = Depends(authenticate)
) -> dict[str, str]:
    """Update a scheduled task."""
    schedules = get_linker_entries_by_schedule_ids([str(payload.schedule_id)])
    if not (schedule := first(schedules, None)):
        raise_status(HTTPStatus.NOT_FOUND, "Schedule does not exist")
    if not (workflow_table := get_workflow_by_workflow_id(str(schedule.workflow_id))):
        raise_status(HTTPStatus.NOT_FOUND, "Task does not exist")

    task_key = workflow_table.name
    task = get_workflow(task_key)

    if task and not await task.authorize_callback(user_model):
        raise_status(HTTPStatus.FORBIDDEN, f"User is not authorized to update schedule with '{task_key}' task")

    add_scheduled_task_to_queue(payload)
    return {"message": "Added to Update Queue", "status": "UPDATED"}


@router.delete("/", status_code=HTTPStatus.OK)
async def delete_scheduled_task(payload: APSchedulerJobDelete) -> dict[str, str]:
    """Delete a scheduled task."""
    add_scheduled_task_to_queue(payload)
    return {"message": "Added to Delete Queue", "status": "DELETED"}

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

from fastapi.routing import APIRouter

from orchestrator.schedules.service import (
    add_create_scheduled_task_to_queue,
    add_delete_scheduled_task_to_queue,
    add_update_scheduled_task_to_queue,
)
from orchestrator.schemas.schedules import APSchedulerJob

router = APIRouter()


@router.post("/", status_code=HTTPStatus.CREATED, response_model=dict[str, str])
def create_scheduled_task(payload: APSchedulerJob) -> dict[str, str]:
    """Create a scheduled task."""
    payload.scheduled_type = "create"  # Override to ensure the correct type
    add_create_scheduled_task_to_queue(payload)
    return {"message": "Added to Create Queue", "status": "CREATED"}


@router.put("/", status_code=HTTPStatus.OK, response_model=dict[str, str])
async def update_scheduled_task(payload: APSchedulerJob) -> dict[str, str]:
    """Update a scheduled task."""
    payload.scheduled_type = "update"  # Override to ensure the correct type
    add_update_scheduled_task_to_queue(payload)
    return {"message": "Added to Update Queue", "status": "UPDATED"}


@router.delete("/", status_code=HTTPStatus.OK, response_model=dict[str, str])
async def delete_scheduled_task(payload: APSchedulerJob) -> dict[str, str]:
    """Delete a scheduled task."""
    payload.scheduled_type = "delete"  # Override to ensure the correct type
    add_delete_scheduled_task_to_queue(payload)
    return {"message": "Added to Delete Queue", "status": "DELETED"}

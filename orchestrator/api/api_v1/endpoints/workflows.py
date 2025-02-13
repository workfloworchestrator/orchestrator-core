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

from http import HTTPStatus
from uuid import UUID

from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from orchestrator.api.error_handling import raise_status
from orchestrator.db import db
from orchestrator.db.models import WorkflowTable
from orchestrator.schemas.workflow import WorkflowPatchSchema, WorkflowSchema

router = APIRouter()


@router.get("/{workflow_id}", response_model=WorkflowSchema)
def get_workflow_description(workflow_id: UUID) -> str:
    workflow = db.session.get(WorkflowTable, workflow_id)
    if workflow is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return workflow


@router.patch("/{workflow_id}", status_code=HTTPStatus.CREATED, response_model=WorkflowSchema)
async def patch_workflow_by_id(workflow_id: UUID, data: WorkflowPatchSchema = Body(...)) -> WorkflowTable:
    workflow = db.session.get(WorkflowTable, workflow_id)
    if not workflow:
        raise_status(HTTPStatus.NOT_FOUND, f"Workflow id {workflow_id} not found")

    return await _patch_workflow_description(data, workflow)


async def _patch_workflow_description(
    data: WorkflowPatchSchema,
    workflow: WorkflowTable,
) -> WorkflowTable:

    updated_properties = data.model_dump(exclude_unset=True)
    description = updated_properties.get("description", workflow.description)
    workflow.description = description
    db.session.commit()
    return workflow

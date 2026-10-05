# Copyright 2019-2026 SURF, GÉANT.
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

"""REST API of the workflow designer, mounted at `/api/workflow-designer` when `WORKFLOW_DESIGNER_ENABLED` is set.

The work behind every endpoint is synchronous (a step scan that takes seconds on first use, the scoped DB session), so
each handler runs it with `run_in_threadpool` to keep the event loop free.
"""

from collections.abc import Callable
from http import HTTPStatus
from typing import Annotated, Literal, NoReturn, TypeVar

from fastapi import Depends, Query
from fastapi.routing import APIRouter
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from orchestrator.core.api.api_v1.endpoints.processes import user_name
from orchestrator.core.api.error_handling import raise_status
from orchestrator.core.settings import app_settings
from orchestrator.core.workflow_designer.definition import ValidationResult, WorkflowDefinition, validate_definition
from orchestrator.core.workflow_designer.discovery import StepInfo, discover_steps
from orchestrator.core.workflow_designer.forms import FIELD_TYPES
from orchestrator.core.workflow_designer.helper_steps import helper_step_infos
from orchestrator.core.workflow_designer.service import (
    DesignerError,
    StoredWorkflow,
    create_workflow,
    delete_workflow,
    get_workflow_definition,
    list_workflows,
    update_workflow,
)

router = APIRouter()

T = TypeVar("T")

_STATUS = {"not_found": HTTPStatus.NOT_FOUND, "conflict": HTTPStatus.CONFLICT, "invalid": HTTPStatus.BAD_REQUEST}


class FieldTypeSchema(BaseModel):
    key: str
    label: str
    options: list[str]


class DesignedWorkflowSchema(BaseModel):
    definition: WorkflowDefinition
    version: int
    created_by: str | None
    process_count: int


class ValidateRequest(BaseModel):
    definition: WorkflowDefinition
    insert_at: int | None = None


class DesignerInfo(BaseModel):
    name_prefix: str
    step_count: int


class DeleteResult(BaseModel):
    result: Literal["deleted", "archived"]


def _schema(stored: StoredWorkflow) -> DesignedWorkflowSchema:
    return DesignedWorkflowSchema(
        definition=stored.definition,
        version=stored.version,
        created_by=stored.created_by,
        process_count=stored.process_count,
    )


async def _call(func: Callable[..., T], *args: object) -> T:
    """Run a service call in the threadpool, mapping its errors to HTTP statuses."""
    try:
        return await run_in_threadpool(func, *args)
    except DesignerError as error:
        _raise(error)


def _raise(error: DesignerError) -> NoReturn:
    raise_status(_STATUS[error.status], {"message": str(error), "validation": error.detail})


def all_steps(rescan: bool = False) -> dict[str, StepInfo]:
    """The designer helpers and every step found in the configured step packages."""
    return {**helper_step_infos(), **discover_steps(rescan=rescan)}


@router.get("/info", response_model=DesignerInfo)
async def info() -> DesignerInfo:
    steps = await run_in_threadpool(all_steps)
    return DesignerInfo(name_prefix=app_settings.WORKFLOW_DESIGNER_NAME_PREFIX, step_count=len(steps))


@router.get("/steps", response_model=list[StepInfo])
async def get_steps(
    rescan: Annotated[
        bool, Query(description="Import the step packages again instead of using the cached scan")
    ] = False,
) -> list[StepInfo]:
    """All steps that can be put in a designed workflow: the designer helpers and every step found in the code."""
    steps = await run_in_threadpool(all_steps, rescan)
    return list(steps.values())


@router.get("/field-types", response_model=list[FieldTypeSchema])
async def get_field_types() -> list[FieldTypeSchema]:
    return [
        FieldTypeSchema(key=field_type.key, label=field_type.label, options=list(field_type.options))
        for field_type in FIELD_TYPES.values()
    ]


@router.post("/validate", response_model=ValidationResult)
async def validate(body: ValidateRequest) -> ValidationResult:
    """Check a definition; with `insert_at`, also tell for each step whether it can be inserted at that position."""
    steps = await run_in_threadpool(all_steps)
    return validate_definition(body.definition, steps, body.insert_at)


@router.get("/workflows", response_model=list[DesignedWorkflowSchema])
async def get_workflows() -> list[DesignedWorkflowSchema]:
    return [_schema(stored) for stored in await _call(list_workflows)]


@router.get("/workflows/{name}", response_model=DesignedWorkflowSchema)
async def get_designed_workflow(name: str) -> DesignedWorkflowSchema:
    return _schema(await _call(get_workflow_definition, name))


@router.post("/workflows", response_model=DesignedWorkflowSchema, status_code=HTTPStatus.CREATED)
async def post_workflow(definition: WorkflowDefinition, user: str = Depends(user_name)) -> DesignedWorkflowSchema:
    return _schema(await _call(create_workflow, definition, user))


@router.put("/workflows/{name}", response_model=DesignedWorkflowSchema)
async def put_workflow(name: str, definition: WorkflowDefinition) -> DesignedWorkflowSchema:
    return _schema(await _call(update_workflow, name, definition))


@router.delete("/workflows/{name}", response_model=DeleteResult)
async def remove_workflow(name: str) -> DeleteResult:
    return DeleteResult(result=await _call(delete_workflow, name))

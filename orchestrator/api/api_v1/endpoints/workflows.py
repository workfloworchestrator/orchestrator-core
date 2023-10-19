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

"""Module that implements workflows related API endpoints."""

from typing import List, Optional

from fastapi.routing import APIRouter

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.schemas import StepSchema, WorkflowSchema, WorkflowWithProductTagsSchema
from orchestrator.workflows import get_workflow

router = APIRouter()


def _add_steps_to_workflow(workflow: WorkflowTable) -> WorkflowSchema:
    def get_steps() -> list[StepSchema]:
        if registered_workflow := get_workflow(workflow.name):
            return [StepSchema(name=step.name) for step in registered_workflow.steps]
        raise AssertionError(f"Workflow {workflow.name} should be registered")

    return WorkflowSchema(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        target=workflow.target,
        description=workflow.description,
        created_at=workflow.created_at,
        steps=get_steps(),
    )


@router.get("/", response_model=List[WorkflowSchema])
def get_all(target: Optional[str] = None, include_steps: bool = False) -> List[WorkflowSchema]:
    query = WorkflowTable.query
    if target:
        query = query.filter(WorkflowTable.__dict__["target"] == target)

    workflows = query.all()

    if include_steps:
        return [_add_steps_to_workflow(workflow) for workflow in workflows]

    return workflows


@router.get("/with_product_tags", response_model=List[WorkflowWithProductTagsSchema])
def get_all_with_product_tags() -> List[WorkflowWithProductTagsSchema]:
    all_workflows = WorkflowTable.query.all()

    def add_product_tags(wf: WorkflowTable) -> WorkflowWithProductTagsSchema:
        tags = (
            ProductTable.query.with_entities(ProductTable.tag.distinct())
            .join(WorkflowTable, ProductTable.workflows)
            .filter(WorkflowTable.workflow_id == wf.workflow_id)
            .all()
        )
        return WorkflowWithProductTagsSchema(
            name=wf.name,
            target=wf.target,
            description=wf.description,
            created_at=wf.created_at,
            product_tags=[t[0] for t in tags],
        )

    return list(map(add_product_tags, all_workflows))

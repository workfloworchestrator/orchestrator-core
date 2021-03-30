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
from orchestrator.schemas import WorkflowSchema, WorkflowWithProductTagsSchema

router = APIRouter()


@router.get("/", response_model=List[WorkflowSchema])
def get_all(target: Optional[str] = None) -> List[WorkflowTable]:
    query = WorkflowTable.query
    if target:
        query = query.filter(WorkflowTable.__dict__["target"] == target)
    return query.all()


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
            product_tags=list(map(lambda t: t[0], tags)),
        )

    return list(map(add_product_tags, all_workflows))

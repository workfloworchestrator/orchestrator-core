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


from fastapi.routing import APIRouter
from sqlalchemy import select

from orchestrator.db import ProductTable, WorkflowTable, db
from orchestrator.schemas import WorkflowSchema, WorkflowWithProductTagsSchema
from orchestrator.services.workflows import get_workflows

router = APIRouter()


@router.get("/", response_model=list[WorkflowSchema])
def get_all(target: str | None = None, include_steps: bool = False) -> list[WorkflowSchema]:
    filters = {"target": target} if target else None
    return list(get_workflows(filters=filters, include_steps=include_steps))


@router.get("/with_product_tags", response_model=list[WorkflowWithProductTagsSchema])
def get_all_with_product_tags() -> list[WorkflowWithProductTagsSchema]:
    all_workflows = get_workflows()

    def add_product_tags(wf: WorkflowSchema) -> WorkflowWithProductTagsSchema:
        products_stmt = (
            select(ProductTable)
            .with_only_columns(ProductTable.tag.distinct())
            .join(WorkflowTable, ProductTable.workflows)
            .filter(WorkflowTable.workflow_id == wf.workflow_id)
        )
        tags = db.session.scalars(products_stmt)
        return WorkflowWithProductTagsSchema(
            name=wf.name,
            target=wf.target,
            description=wf.description,
            created_at=wf.created_at,
            product_tags=[t[0] for t in tags],
        )

    return list(map(add_product_tags, all_workflows))

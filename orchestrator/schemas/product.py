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

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.fixed_input import FixedInputSchema
from orchestrator.schemas.product_block import ProductBlockSchema
from orchestrator.schemas.workflow import WorkflowSchema


class ProductBaseSchema(OrchestratorBaseModel):
    product_id: UUID | None = None
    name: str
    description: str
    product_type: str
    status: ProductLifecycle
    tag: str
    created_at: datetime | None = None
    end_date: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ProductSchema(ProductBaseSchema):
    product_id: UUID
    created_at: datetime
    product_blocks: list[ProductBlockSchema]
    fixed_inputs: list[FixedInputSchema]
    workflows: list[WorkflowSchema]

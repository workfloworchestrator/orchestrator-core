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
from typing import List, Optional
from uuid import UUID

from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.fixed_input import FixedInputBaseSchema, FixedInputSchema
from orchestrator.schemas.product_block import ProductBlockBaseSchema, ProductBlockSchema
from orchestrator.schemas.workflow import WorkflowSchema


class ProductBaseSchema(OrchestratorBaseModel):
    product_id: Optional[UUID]
    name: str
    description: str
    product_type: str
    status: ProductLifecycle
    tag: str
    created_at: Optional[datetime]
    end_date: Optional[datetime]

    class Config:
        orm_mode = True


class ProductSchema(ProductBaseSchema):
    product_id: UUID
    created_at: datetime
    product_blocks: List[ProductBlockSchema]
    fixed_inputs: List[FixedInputSchema]
    workflows: List[WorkflowSchema]


class ProductCRUDSchema(ProductBaseSchema):
    product_blocks: Optional[List[ProductBlockBaseSchema]]
    fixed_inputs: Optional[List[FixedInputBaseSchema]]

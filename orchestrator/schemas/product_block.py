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
from orchestrator.schemas.resource_type import ResourceTypeBaseSchema, ResourceTypeSchemaORM


class ProductBlockBaseSchema(OrchestratorBaseModel):
    product_block_id: Optional[UUID]
    name: str
    description: str
    tag: Optional[str]
    status: Optional[ProductLifecycle]
    resource_types: Optional[List[ResourceTypeBaseSchema]]


class ProductBlockEnrichedSchema(OrchestratorBaseModel):
    product_block_id: UUID
    name: str
    description: str
    tag: Optional[str]
    status: ProductLifecycle
    created_at: Optional[datetime]
    end_date: Optional[datetime]
    resource_types: Optional[List[ResourceTypeSchemaORM]]

    class Config:
        orm_mode = True


class ProductBlockSchema(ProductBlockBaseSchema):
    product_block_id: UUID
    status: ProductLifecycle
    created_at: datetime
    end_date: Optional[datetime]
    resource_types: Optional[List[ResourceTypeSchemaORM]]  # type: ignore

    class Config:
        orm_mode = True

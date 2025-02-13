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
from orchestrator.schemas.resource_type import ResourceTypeBaseSchema, ResourceTypeSchema


class ProductBlockBaseSchema(OrchestratorBaseModel):
    product_block_id: UUID | None = None
    name: str
    description: str
    tag: str | None = None
    status: ProductLifecycle | None = None
    resource_types: list[ResourceTypeBaseSchema] | None = None


class ProductBlockSchema(ProductBlockBaseSchema):
    product_block_id: UUID
    status: ProductLifecycle
    created_at: datetime
    end_date: datetime | None = None
    resource_types: list[ResourceTypeSchema] | None = None  # type: ignore
    model_config = ConfigDict(from_attributes=True)


class ProductBlockPatchSchema(OrchestratorBaseModel):
    description: str | None = None

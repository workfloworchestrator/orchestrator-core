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

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from orchestrator.core.domain.lifecycle import ProductLifecycle
from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.schemas.resource_type import ResourceTypeSchema


class ProductBlockRelationIndexSchema(OrchestratorBaseModel):
    """Minimal product block summary embedded in a product block's search index entry."""

    model_config = ConfigDict(from_attributes=True)
    product_block_id: UUID
    name: str


class ProductBlockIndexSchema(OrchestratorBaseModel):
    """Product block definition and related product block definitions, for search indexing only."""

    model_config = ConfigDict(from_attributes=True)
    product_block_id: UUID
    name: str
    description: str
    status: ProductLifecycle
    tag: str | None = None
    created_at: datetime
    end_date: datetime | None = None
    resource_types: list[ResourceTypeSchema] = []
    in_use_by: list[ProductBlockRelationIndexSchema] = []

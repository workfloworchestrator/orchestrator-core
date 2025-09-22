# Copyright 2019-2025 SURF, GÉANT.
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

from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.orm import Query
from sqlalchemy.sql import Select

from orchestrator.db import (
    ProcessTable,
    ProductTable,
    SubscriptionTable,
    WorkflowTable,
)
from orchestrator.db.database import BaseModel
from orchestrator.search.core.types import EntityType

from .traverse import (
    BaseTraverser,
    ProcessTraverser,
    ProductTraverser,
    SubscriptionTraverser,
    WorkflowTraverser,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class EntityConfig(Generic[ModelT]):
    """A container for all configuration related to a specific entity type."""

    entity_kind: EntityType
    table: type[ModelT]

    traverser: "type[BaseTraverser]"
    pk_name: str
    root_name: str

    def get_all_query(self, entity_id: str | None = None) -> Query | Select:
        query = self.table.query
        if entity_id:
            pk_column = getattr(self.table, self.pk_name)
            query = query.filter(pk_column == UUID(entity_id))
        return query


@dataclass(frozen=True)
class WorkflowConfig(EntityConfig[WorkflowTable]):
    """Workflows have a custom select() function that filters out deleted workflows."""

    def get_all_query(self, entity_id: str | None = None) -> Select:
        query = self.table.select()
        if entity_id:
            pk_column = getattr(self.table, self.pk_name)
            query = query.where(pk_column == UUID(entity_id))
        return query


ENTITY_CONFIG_REGISTRY: dict[EntityType, EntityConfig] = {
    EntityType.SUBSCRIPTION: EntityConfig(
        entity_kind=EntityType.SUBSCRIPTION,
        table=SubscriptionTable,
        traverser=SubscriptionTraverser,
        pk_name="subscription_id",
        root_name="subscription",
    ),
    EntityType.PRODUCT: EntityConfig(
        entity_kind=EntityType.PRODUCT,
        table=ProductTable,
        traverser=ProductTraverser,
        pk_name="product_id",
        root_name="product",
    ),
    EntityType.PROCESS: EntityConfig(
        entity_kind=EntityType.PROCESS,
        table=ProcessTable,
        traverser=ProcessTraverser,
        pk_name="process_id",
        root_name="process",
    ),
    EntityType.WORKFLOW: WorkflowConfig(
        entity_kind=EntityType.WORKFLOW,
        table=WorkflowTable,
        traverser=WorkflowTraverser,
        pk_name="workflow_id",
        root_name="workflow",
    ),
}

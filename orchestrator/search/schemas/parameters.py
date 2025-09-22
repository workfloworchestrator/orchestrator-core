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

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.search.core.types import ActionType, EntityType
from orchestrator.search.filters import FilterTree


class BaseSearchParameters(BaseModel):
    """Base model with common search parameters."""

    action: ActionType = Field(default=ActionType.SELECT, description="The action to perform.")
    entity_type: EntityType

    filters: FilterTree | None = Field(default=None, description="A list of structured filters to apply to the search.")

    query: str | None = Field(
        default=None, description="Unified search query - will be processed into vector_query and/or fuzzy_term"
    )

    limit: int = Field(default=10, ge=1, le=30, description="Maximum number of search results to return.")
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def create(cls, entity_type: EntityType, **kwargs: Any) -> "BaseSearchParameters":
        try:
            return PARAMETER_REGISTRY[entity_type](entity_type=entity_type, **kwargs)
        except KeyError:
            raise ValueError(f"No search parameter class found for entity type: {entity_type.value}")

    @property
    def vector_query(self) -> str | None:
        """Extract vector query from unified query field."""
        if not self.query:
            return None
        try:
            uuid.UUID(self.query)
            return None  # It's a UUID, so disable vector search.
        except ValueError:
            return self.query

    @property
    def fuzzy_term(self) -> str | None:
        """Extract fuzzy term from unified query field."""
        if not self.query:
            return None

        words = self.query.split()
        # Only use fuzzy for single words
        # otherwise, trigram operator filters out too much.
        return self.query if len(words) == 1 else None


class SubscriptionSearchParameters(BaseSearchParameters):
    entity_type: Literal[EntityType.SUBSCRIPTION] = Field(
        default=EntityType.SUBSCRIPTION, description="The type of entity to search."
    )
    model_config = ConfigDict(
        json_schema_extra={
            "title": "SearchSubscriptions",
            "description": "Search subscriptions based on specific criteria.",
            "examples": [
                {
                    "filters": {
                        "op": "AND",
                        "children": [
                            {"path": "subscription.status", "condition": {"op": "eq", "value": "provisioning"}},
                            {"path": "subscription.end_date", "condition": {"op": "gte", "value": "2025-01-01"}},
                        ],
                    }
                }
            ],
        }
    )


class ProductSearchParameters(BaseSearchParameters):
    entity_type: Literal[EntityType.PRODUCT] = Field(
        default=EntityType.PRODUCT, description="The type of entity to search."
    )
    model_config = ConfigDict(
        json_schema_extra={
            "title": "SearchProducts",
            "description": "Search products based on specific criteria.",
            "examples": [
                {
                    "filters": [
                        {"path": "product.product_type", "condition": {"op": "eq", "value": "Shop"}},
                    ]
                }
            ],
        }
    )


class WorkflowSearchParameters(BaseSearchParameters):
    entity_type: Literal[EntityType.WORKFLOW] = Field(
        default=EntityType.WORKFLOW, description="The type of entity to search."
    )


class ProcessSearchParameters(BaseSearchParameters):
    """Search parameters specifically for PROCESS entities."""

    entity_type: Literal[EntityType.PROCESS] = Field(
        default=EntityType.PROCESS, description="The type of entity to search."
    )


PARAMETER_REGISTRY: dict[EntityType, type[BaseSearchParameters]] = {
    EntityType.SUBSCRIPTION: SubscriptionSearchParameters,
    EntityType.PRODUCT: ProductSearchParameters,
    EntityType.WORKFLOW: WorkflowSearchParameters,
    EntityType.PROCESS: ProcessSearchParameters,
}

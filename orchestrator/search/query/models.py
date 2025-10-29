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
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from orchestrator.search.aggregations import Aggregation, TemporalGrouping, TemporalPeriod
from orchestrator.search.core.types import ActionType, EntityType
from orchestrator.search.filters import FilterTree


class BaseQuery(BaseModel):
    """Base model for all search queries."""

    MAX_LIMIT: ClassVar[int] = 30
    DEFAULT_EXPORT_LIMIT: ClassVar[int] = 1000
    MAX_EXPORT_LIMIT: ClassVar[int] = 10000

    action: ActionType = Field(
        default=ActionType.SELECT,
        description=(
            "The action to perform. "
            "Use 'select' to find and return entities. "
            "Use 'count' for counting, optionally grouped (keywords: 'how many', 'count', 'over time', 'per', 'by'). "
            "Use 'aggregate' for statistics (keywords: 'average', 'sum', 'total', 'min', 'max')."
        ),
    )
    entity_type: EntityType

    filters: FilterTree | None = Field(default=None, description="A list of structured filters to apply to the search.")

    query: str | None = Field(
        default=None, description="Unified search query - will be processed into vector_query and/or fuzzy_term"
    )

    limit: int = Field(default=10, ge=1, le=MAX_LIMIT, description="Maximum number of search results to return.")
    export_limit: int = Field(
        default=DEFAULT_EXPORT_LIMIT, ge=1, le=MAX_EXPORT_LIMIT, description="Maximum number of results to export."
    )

    # Aggregation-specific fields
    group_by: list[str] | None = Field(
        default=None,
        description="List of field paths to group by. Used with COUNT and AGGREGATE actions.",
    )
    temporal_group_by: list[TemporalGrouping] | None = Field(
        default=None,
        description="List of temporal groupings for datetime fields (group by month, year, etc.). Used with COUNT and AGGREGATE actions.",
    )
    aggregations: list[Aggregation] | None = Field(
        default=None,
        description="List of aggregations to compute. Used with AGGREGATE action.",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_action_requirements(self) -> "BaseQuery":
        """Validate that aggregation/grouping fields are only used with appropriate actions."""
        # Temporal grouping
        if self.temporal_group_by and self.action not in (ActionType.COUNT, ActionType.AGGREGATE):
            raise ValueError(
                f"temporal_group_by is only valid for COUNT and AGGREGATE actions. Got action={self.action}"
            )

        # Aggregations
        if self.aggregations and self.action != ActionType.AGGREGATE:
            raise ValueError(f"aggregations is only valid for AGGREGATE action. Got action={self.action}")

        # GROUP BY
        if self.group_by and self.action not in (ActionType.COUNT, ActionType.AGGREGATE):
            raise ValueError(f"group_by is only valid for COUNT and AGGREGATE actions. Got action={self.action}")

        # Validate group_by paths are not empty
        if self.group_by:
            for path in self.group_by:
                if not path or not path.strip():
                    raise ValueError(f"group_by contains empty or whitespace-only path: '{path}'")

        return self

    @classmethod
    def create(cls, **kwargs: Any) -> "QueryTypes":
        """Create the correct query subclass instance based on entity_type."""
        from orchestrator.search.query.models import QueryTypes

        adapter: TypeAdapter = TypeAdapter(QueryTypes)
        return adapter.validate_python(kwargs)

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

    def get_pivot_fields(self) -> list[str]:
        """Collect all fields that need pivoting from EAV to columns.

        Returns deduplicated list maintaining insertion order.
        """
        fields = list(self.group_by or [])

        # Collect from temporal groupings
        if self.temporal_group_by:
            for temp_group in self.temporal_group_by:
                fields.extend(temp_group.get_pivot_fields())

        # Collect from aggregations
        if self.aggregations:
            for agg in self.aggregations:
                fields.extend(agg.get_pivot_fields())

        return list(dict.fromkeys(fields))


class SubscriptionQuery(BaseQuery):
    entity_type: Literal[EntityType.SUBSCRIPTION] = Field(
        default=EntityType.SUBSCRIPTION, description="The type of entity to query."
    )
    model_config = ConfigDict(
        json_schema_extra={
            "title": "QuerySubscriptions",
            "description": "Query subscriptions based on specific criteria.",
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


class ProductQuery(BaseQuery):
    entity_type: Literal[EntityType.PRODUCT] = Field(
        default=EntityType.PRODUCT, description="The type of entity to query."
    )
    model_config = ConfigDict(
        json_schema_extra={
            "title": "QueryProducts",
            "description": "Query products based on specific criteria.",
            "examples": [
                {
                    "filters": [
                        {"path": "product.product_type", "condition": {"op": "eq", "value": "Shop"}},
                    ]
                }
            ],
        }
    )


class WorkflowQuery(BaseQuery):
    entity_type: Literal[EntityType.WORKFLOW] = Field(
        default=EntityType.WORKFLOW, description="The type of entity to query."
    )


class ProcessQuery(BaseQuery):
    """Query specifically for PROCESS entities."""

    entity_type: Literal[EntityType.PROCESS] = Field(
        default=EntityType.PROCESS, description="The type of entity to query."
    )


QueryTypes = SubscriptionQuery | ProductQuery | WorkflowQuery | ProcessQuery

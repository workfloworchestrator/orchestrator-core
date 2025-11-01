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

from typing import Annotated, Any, ClassVar, Literal, Self, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field

from orchestrator.search.core.types import ActionType, EntityType
from orchestrator.search.filters import FilterTree

from .mixins import (
    AggregationMixin,
    GroupingMixin,
    SearchMixin,
)


class BaseQuery(BaseModel):
    """Base model for all query types.

    Contains shared constants, properties, and utilities.
    """

    MIN_LIMIT: ClassVar[int] = 1
    DEFAULT_LIMIT: ClassVar[int] = 10
    MAX_LIMIT: ClassVar[int] = 30
    DEFAULT_EXPORT_LIMIT: ClassVar[int] = 1000
    MAX_EXPORT_LIMIT: ClassVar[int] = 10000

    _action: ClassVar[ActionType]

    entity_type: EntityType
    filters: FilterTree | None = Field(default=None, description="Structured filters to apply")

    model_config = ConfigDict(extra="forbid")

    @property
    def action(self) -> ActionType:
        return self._action

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build query from a dictionary.

        Args:
            data: Dictionary with query parameters

        Returns:
            Query instance of the appropriate type
        """
        return cls.model_validate(data)


class SelectQuery(BaseQuery, SearchMixin):
    """Query for SELECT operations.

    Composes BaseQuery with SearchMixin for text search, with strict result limits.
    """

    query_type: Literal["select"] = "select"
    _action: ClassVar[ActionType] = ActionType.SELECT

    limit: int = Field(
        default=BaseQuery.DEFAULT_LIMIT,
        ge=BaseQuery.MIN_LIMIT,
        le=BaseQuery.MAX_LIMIT,
        description="Maximum number of search results to return",
    )


class ExportQuery(BaseQuery, SearchMixin):
    """Query for EXPORT operations .

    Similar to SelectQuery but with higher limits for bulk exports.
    """

    query_type: Literal["export"] = "export"
    _action: ClassVar[ActionType] = ActionType.SELECT

    limit: int = Field(
        default=BaseQuery.DEFAULT_EXPORT_LIMIT,
        ge=BaseQuery.MIN_LIMIT,
        le=BaseQuery.MAX_EXPORT_LIMIT,
        description="Maximum number of results to export",
    )


class CountQuery(BaseQuery, GroupingMixin):
    """Query for COUNT operations with optional grouping."""

    query_type: Literal["count"] = "count"
    _action: ClassVar[ActionType] = ActionType.COUNT


class AggregateQuery(BaseQuery, GroupingMixin, AggregationMixin):
    """Query for AGGREGATE operations.

    Composes BaseQuery with GroupingMixin and AggregationMixin
    to provide both grouping and aggregation capabilities.
    """

    query_type: Literal["aggregate"] = "aggregate"
    _action: ClassVar[ActionType] = ActionType.AGGREGATE

    def get_pivot_fields(self) -> list[str]:
        """Get all fields needed for EAV pivot including aggregation fields."""
        # Get grouping fields from GroupingMixin
        fields = super().get_pivot_fields()

        # Add aggregation fields
        fields.extend(self.get_aggregation_pivot_fields())

        return list(dict.fromkeys(fields))


Query = Annotated[
    Union[SelectQuery, ExportQuery, CountQuery, AggregateQuery],
    Discriminator("query_type"),
]

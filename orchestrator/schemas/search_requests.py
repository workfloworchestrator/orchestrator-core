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


from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from orchestrator.search.core.types import EntityType, RetrieverType
from orchestrator.search.filters import ElasticQuery, FilterTree, elastic_to_filter_tree
from orchestrator.search.query.mixins import StructuredOrderBy
from orchestrator.search.query.queries import SelectQuery

# Keys that identify an ES DSL query at the top level
_ES_DSL_KEYS = frozenset({"term", "range", "wildcard", "exists", "bool"})
_ES_QUERY_ADAPTER: TypeAdapter[ElasticQuery] = TypeAdapter(ElasticQuery)


class SearchRequest(BaseModel):
    """API request model for search operations.

    Only supports SELECT action, used by search endpoints.
    Accepts filters in either FilterTree format or Elasticsearch DSL format.
    ES DSL filters are auto-converted to FilterTree before processing.
    """

    filters: FilterTree | None = Field(
        default=None,
        description="Structured filters to apply to the search. Accepts FilterTree or Elasticsearch DSL format.",
    )

    @field_validator("filters", mode="before")
    @classmethod
    def _convert_elastic_dsl_filters(cls, value: Any) -> Any:
        """Detect and convert ES DSL filters to FilterTree before validation."""
        if isinstance(value, dict) and _ES_DSL_KEYS & value.keys():
            es_query = _ES_QUERY_ADAPTER.validate_python(value)
            return elastic_to_filter_tree(es_query).model_dump()
        return value

    query: str | None = Field(
        default=None,
        description="Text search query for semantic/fuzzy search.",
    )
    limit: int = Field(
        default=SelectQuery.DEFAULT_LIMIT,
        ge=SelectQuery.MIN_LIMIT,
        le=SelectQuery.MAX_LIMIT,
        description="Maximum number of search results to return.",
    )
    retriever: RetrieverType | None = Field(
        default=None,
        description="Force a specific retriever type. If None, uses default routing logic.",
    )
    order_by: StructuredOrderBy | None = Field(
        default=None,
        description="Ordering instructions for search results, only applied with structured search.",
    )

    model_config = ConfigDict(extra="forbid")

    def to_query(self, entity_type: EntityType) -> SelectQuery:
        """Convert API request to SelectQuery domain model.

        Args:
            entity_type: The entity type to search (provided by endpoint)

        Returns:
            SelectQuery for search operation
        """
        return SelectQuery(
            entity_type=entity_type,
            filters=self.filters,
            query_text=self.query,
            limit=self.limit,
            retriever=self.retriever,
            order_by=self.order_by,
        )

    @model_validator(mode="after")
    def validate_order_by_not_compatible_with_query(self) -> "SearchRequest":
        if self.order_by and self.query:
            raise ValueError("order_by can only be set when query is empty")
        return self

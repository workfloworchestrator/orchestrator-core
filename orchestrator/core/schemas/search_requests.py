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


from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, TypeAdapter, model_validator

from orchestrator.core.search.core.types import EntityType, FieldType, RetrieverType, UIType
from orchestrator.core.search.filters import ElasticQuery, FilterTree, elastic_to_filter_tree
from orchestrator.core.search.indexing.field_types import resolve_field_types
from orchestrator.core.search.query.mixins import StructuredOrderBy
from orchestrator.core.search.query.queries import SelectQuery

# Keys that identify an ES DSL query at the top level
_ES_DSL_KEYS = frozenset({"term", "range", "wildcard", "regexp", "exists", "bool"})
_ES_QUERY_ADAPTER: TypeAdapter[ElasticQuery] = TypeAdapter(ElasticQuery)


def _resolve_digit_only_string_kind(entity_type: EntityType, path: str) -> UIType | None:
    field_types = resolve_field_types(entity_type, path)
    if field_types == {FieldType.STRING}:
        return UIType.STRING
    if field_types and field_types <= {FieldType.INTEGER, FieldType.FLOAT}:
        return UIType.NUMBER
    return None


class SearchRequest(BaseModel):
    """API request model for search operations.

    Only supports SELECT action, used by search endpoints.
    Accepts filters in either FilterTree format or Elasticsearch DSL format.
    ES DSL filters are validated on receipt and converted after the entity type is known.
    """

    filters: FilterTree | None = Field(
        default=None,
        description="Structured filters to apply to the search. Accepts FilterTree or Elasticsearch DSL format.",
    )
    _elastic_filters: ElasticQuery | None = PrivateAttr(default=None)

    @model_validator(mode="wrap")
    @classmethod
    def _parse_elastic_dsl_filters(cls, value: Any, handler: Any) -> "SearchRequest":
        """Validate ES DSL while retaining it for entity-aware conversion in to_query."""
        if not isinstance(value, dict):
            return handler(value)

        raw_filters = value.get("filters")
        if not (isinstance(raw_filters, dict) and _ES_DSL_KEYS & raw_filters.keys()):
            return handler(value)

        parsed_filters = _ES_QUERY_ADAPTER.validate_python(raw_filters)
        input_data = dict(value)
        input_data["filters"] = None
        request = handler(input_data)
        request._elastic_filters = parsed_filters
        return request

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
    response_columns: list[str] | None = Field(
        default=None,
        description="Field paths to return as inline columns on each search result.",
    )

    model_config = ConfigDict(extra="forbid")

    def to_query(self, entity_type: EntityType) -> SelectQuery:
        """Convert API request to SelectQuery domain model.

        Args:
            entity_type: The entity type to search (provided by endpoint)

        Returns:
            SelectQuery for search operation
        """
        filters = self.filters
        if self._elastic_filters is not None:
            filters = elastic_to_filter_tree(
                self._elastic_filters,
                value_kind_resolver=lambda path, _value: _resolve_digit_only_string_kind(entity_type, path),
            )

        return SelectQuery(
            entity_type=entity_type,
            filters=filters,
            query_text=self.query,
            limit=self.limit,
            retriever=self.retriever,
            order_by=self.order_by,
            response_columns=self.response_columns,
        )

    @model_validator(mode="after")
    def validate_order_by_not_compatible_with_query(self) -> "SearchRequest":
        if self.order_by and self.query:
            raise ValueError("order_by can only be set when query is empty")
        return self

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


from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.filters import ElasticQuery, FilterTree, elastic_to_filter_tree
from orchestrator.core.search.indexing.field_types import resolve_field_value_kind
from orchestrator.core.search.query.mixins import StructuredOrderBy
from orchestrator.core.search.query.queries import BaseQuery, ExportQuery, SelectQuery


class BaseSearchRequest(BaseModel):
    """Fields shared by the search and export request models.

    Accepts filters in either FilterTree format or Elasticsearch DSL format.
    ES DSL filters are converted to FilterTree in to_query, once the entity type is known.
    """

    filters: FilterTree | ElasticQuery | None = Field(
        default=None,
        description="Structured filters to apply to the search. Accepts FilterTree or Elasticsearch DSL format.",
    )

    query: str | None = Field(
        default=None,
        description="Text search query for semantic/fuzzy search.",
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

    def filter_tree(self, entity_type: EntityType) -> FilterTree | None:
        """Return the filters as a FilterTree, converting ES DSL filters for the given entity type."""
        if isinstance(self.filters, ElasticQuery):
            return elastic_to_filter_tree(
                self.filters,
                value_kind_resolver=lambda path, _value: resolve_field_value_kind(entity_type, path),
            )
        return self.filters

    @model_validator(mode="after")
    def validate_order_by_not_compatible_with_query(self) -> Self:
        if self.order_by and self.query:
            raise ValueError("order_by can only be set when query is empty")
        return self


class SearchRequest(BaseSearchRequest):
    """API request model for search operations.

    Only supports SELECT action, used by search endpoints.
    """

    limit: int = Field(
        default=SelectQuery.DEFAULT_LIMIT,
        ge=SelectQuery.MIN_LIMIT,
        le=SelectQuery.MAX_LIMIT,
        description="Maximum number of search results to return.",
    )

    def to_query(self, entity_type: EntityType) -> SelectQuery:
        """Convert API request to SelectQuery domain model.

        Args:
            entity_type: The entity type to search (provided by endpoint)

        Returns:
            SelectQuery for search operation
        """
        return SelectQuery(
            entity_type=entity_type,
            filters=self.filter_tree(entity_type),
            query_text=self.query,
            limit=self.limit,
            retriever=self.retriever,
            order_by=self.order_by,
            response_columns=self.response_columns,
        )


class SearchExportRequest(BaseSearchRequest):
    """API request model for exporting search results.

    Same as SearchRequest, but the limit is bounded by the export limit (`SEARCH_MAX_EXPORT_LIMIT`)
    and defaults to it.
    """

    limit: int = Field(
        default=BaseQuery.MAX_EXPORT_LIMIT,
        ge=BaseQuery.MIN_LIMIT,
        le=BaseQuery.MAX_EXPORT_LIMIT,
        description="Maximum number of search results to export. Defaults to the maximum.",
    )

    def to_query(self, entity_type: EntityType) -> ExportQuery:
        """Convert API request to ExportQuery domain model.

        Args:
            entity_type: The entity type to export (provided by endpoint)

        Returns:
            ExportQuery for export operation
        """
        return ExportQuery(
            entity_type=entity_type,
            filters=self.filter_tree(entity_type),
            query_text=self.query,
            limit=self.limit,
            retriever=self.retriever,
            order_by=self.order_by,
            response_columns=self.response_columns,
        )

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


from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy_utils import Ltree

from orchestrator.search.core.types import EntityType, RetrieverType
from orchestrator.search.filters import FilterTree
from orchestrator.search.query.mixins import StructuredOrderBy
from orchestrator.search.query.queries import SelectQuery


class SearchRequest(BaseModel):
    """API request model for search operations.

    Only supports SELECT action, used by search endpoints.
    """

    filters: FilterTree | None = Field(
        default=None,
        description="Structured filters to apply to the search.",
    )
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


async def validate_order_by_element(entity_type: EntityType | None, request: SearchRequest | None) -> None:
    from orchestrator.db import db
    from orchestrator.db.models import AiSearchIndex

    if not request or not request.order_by or not entity_type:
        return

    element = request.order_by.element

    stmt = (
        select(AiSearchIndex.path)
        .where(AiSearchIndex.entity_type == entity_type.value, AiSearchIndex.path == Ltree(element))
        .limit(1)
    )

    exists = db.session.execute(stmt).all()
    if not exists:
        raise ValueError(f"Element {element} is not a valid path")

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


from pydantic import BaseModel, ConfigDict, Field

from orchestrator.search.core.types import EntityType
from orchestrator.search.filters import FilterTree
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
        )

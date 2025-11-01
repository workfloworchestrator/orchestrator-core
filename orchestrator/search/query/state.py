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

from typing import Generic, TypeVar, cast
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict, Field

from orchestrator.db import SearchQueryTable, db
from orchestrator.search.core.exceptions import QueryStateNotFoundError
from orchestrator.search.query.queries import BaseQuery, Query

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=Query)


class QueryState(BaseModel, Generic[T]):
    """State of a query including parameters and embedding.

    Thin wrapper around SearchQueryTable that stores query as JSONB blob.
    Generic over query type for type-safe loading.
    Used for both agent and regular API queries.
    """

    query: T
    query_embedding: list[float] | None = Field(default=None, description="The embedding vector for semantic search")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def load_from_id(cls, query_id: UUID | str, expected_type: type[T]) -> "QueryState[T]":
        """Load query state from database by query_id with type validation.

        Args:
            query_id: UUID or string UUID of the saved query
            expected_type: Expected query type class (SelectQuery, ExportQuery, etc.)

        Returns:
            QueryState with validated query type

        Raises:
            ValueError: If query_id format is invalid or query type doesn't match expected
            QueryStateNotFoundError: If query not found in database
        """
        if isinstance(query_id, UUID):
            query_uuid = query_id
        else:
            try:
                query_uuid = UUID(query_id)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid query_id format: {query_id}") from e

        search_query = db.session.query(SearchQueryTable).filter_by(query_id=query_uuid).first()
        if not search_query:
            raise QueryStateNotFoundError(f"Query {query_uuid} not found in database")

        # Clamp limit to valid range to handle legacy queries outside the current limits
        if "limit" in search_query.parameters and search_query.parameters["limit"] > BaseQuery.MAX_LIMIT:
            logger.warning(
                "Loaded query limit exceeds maximum, clamping to MAX_LIMIT",
                query_id=query_uuid,
                original_limit=search_query.parameters["limit"],
                clamped_to=BaseQuery.MAX_LIMIT,
            )
            search_query.parameters["limit"] = BaseQuery.MAX_LIMIT

        query = cast(T, expected_type.from_dict(search_query.parameters))

        return cls(query=query, query_embedding=search_query.query_embedding)

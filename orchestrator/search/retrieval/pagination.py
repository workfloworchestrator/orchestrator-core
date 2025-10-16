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

import base64
from dataclasses import dataclass

from pydantic import BaseModel

from orchestrator.db import SearchQueryTable, db
from orchestrator.search.core.exceptions import InvalidCursorError
from orchestrator.search.schemas.parameters import SearchParameters, SearchQueryState
from orchestrator.search.schemas.results import SearchResult


@dataclass
class PaginationParams:
    """Parameters for pagination in search queries."""

    page_after_score: float | None = None
    page_after_id: str | None = None
    q_vec_override: list[float] | None = None
    query_id: str | None = None


class PageCursor(BaseModel):
    score: float
    id: str
    query_id: str | None = None

    def encode(self) -> str:
        """Encode the cursor data into a URL-safe Base64 string."""
        json_str = self.model_dump_json()
        return base64.urlsafe_b64encode(json_str.encode("utf-8")).decode("utf-8")

    @classmethod
    def decode(cls, cursor: str) -> "PageCursor":
        """Decode a Base64 string back into a PageCursor instance."""
        try:
            decoded_str = base64.urlsafe_b64decode(cursor).decode("utf-8")
            return cls.model_validate_json(decoded_str)
        except Exception as e:
            raise InvalidCursorError("Invalid pagination cursor") from e


async def process_pagination_cursor(cursor: str | None, search_params: SearchParameters) -> PaginationParams:
    """Process pagination cursor and return pagination parameters."""
    if cursor:
        c = PageCursor.decode(cursor)

        # If cursor has query_id, retrieve saved embedding
        if c.query_id:
            query = db.session.query(SearchQueryTable).filter_by(query_id=c.query_id).first()
            if not query:
                raise InvalidCursorError("Query not found")

            query_state = query.to_state()

            return PaginationParams(
                page_after_score=c.score,
                page_after_id=c.id,
                q_vec_override=query_state.query_embedding,
                query_id=c.query_id,
            )

        # No query_id - filter-only or fuzzy-only search
        return PaginationParams(
            page_after_score=c.score,
            page_after_id=c.id,
        )

    # First page, no embedding needed
    # Engine will generate it
    return PaginationParams()


def create_next_page_cursor(
    search_results: list[SearchResult],
    pagination_params: PaginationParams,
    limit: int,
    search_params: SearchParameters | None = None,
) -> str | None:
    """Create next page cursor if there are more results.

    On first page with hybrid search (embedding present), saves the query to database
    and includes query_id in cursor for subsequent pages.
    """
    has_next_page = len(search_results) == limit and limit > 0
    if not has_next_page:
        return None

    # If this is the first page and we have an embedding, save to database
    if not pagination_params.query_id and pagination_params.q_vec_override and search_params:
        # Create query state and save to database
        query_state = SearchQueryState(parameters=search_params, query_embedding=pagination_params.q_vec_override)
        search_query = SearchQueryTable.from_state(state=query_state)

        db.session.add(search_query)
        db.session.commit()
        pagination_params.query_id = str(search_query.query_id)

    last_item = search_results[-1]
    cursor_data = PageCursor(
        score=float(last_item.score),
        id=last_item.entity_id,
        query_id=pagination_params.query_id,
    )
    return cursor_data.encode()

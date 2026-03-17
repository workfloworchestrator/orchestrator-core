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
from uuid import UUID

from pydantic import BaseModel

from orchestrator.db import SearchQueryTable, db
from orchestrator.search.core.exceptions import InvalidCursorError
from orchestrator.search.query.queries import SelectQuery
from orchestrator.search.query.results import SearchResponse


class PageCursor(BaseModel):
    score: float
    id: str
    query_id: UUID

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


def encode_next_page_cursor(
    search_response: SearchResponse,
    cursor: PageCursor | None,
    query: SelectQuery,
) -> str | None:
    """Create next page cursor if there are more results.

    On first page, saves the query to database and includes query_id in cursor
    for subsequent pages to ensure consistent parameters across pagination.

    Args:
        search_response: SearchResponse containing results and query_embedding
        cursor: Current page cursor (None for first page, PageCursor for subsequent pages)
        query: SelectQuery for search operation to save for pagination consistency

    Returns:
        Encoded cursor for next page, or None if no more results
    """
    from orchestrator.search.query.state import QueryState

    if not search_response.has_more:
        return None

    # If this is the first page, save query state to database
    if cursor is None:
        query_state = QueryState(query=query, query_embedding=search_response.query_embedding)
        search_query = SearchQueryTable.from_state(state=query_state)

        db.session.add(search_query)
        db.session.commit()
        query_id = search_query.query_id
    else:
        query_id = cursor.query_id

    last_item = search_response.results[-1]
    cursor_data = PageCursor(
        score=float(last_item.score),
        id=last_item.entity_id,
        query_id=query_id,
    )
    return cursor_data.encode()

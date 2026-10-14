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

"""One page of a select search, shared by the REST and GraphQL search endpoints.

Each endpoint converts the page to its own response type and maps the raised errors to its own transport.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.search.core.exceptions import InvalidCursorError
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.query.results import SearchResponse
from orchestrator.core.search.query.state import QueryState
from orchestrator.core.search.retrieval.pagination import PageCursor, encode_next_page_cursor
from orchestrator.core.search.retrieval.retrievers import Retriever


@dataclass(frozen=True)
class SearchPage:
    response: SearchResponse
    next_page_cursor: str | None

    @property
    def entity_ids(self) -> list[str]:
        return [result.entity_id for result in self.response.results]


async def _load_query_state(
    session: AsyncSession,
    query: SelectQuery | None,
    cursor: PageCursor | None,
    query_id: str | None,
    entity_type: EntityType | None,
) -> QueryState[SelectQuery]:
    if cursor:
        query_state = await QueryState.load_from_id(cursor.query_id, SelectQuery, session)
        # A cursor is only bound to a saved query, so one from another entity's search would silently page it.
        if entity_type and query_state.query.entity_type != entity_type:
            raise InvalidCursorError(f"Cursor belongs to a {query_state.query.entity_type.value} search")
        return query_state
    if query_id:
        return await QueryState.load_from_id(query_id, SelectQuery, session)
    if query:
        return QueryState(query=query, query_embedding=None)
    raise ValueError("Either query, cursor or query_id must be provided")


async def execute_search_page(
    session: AsyncSession,
    *,
    query: SelectQuery | None = None,
    cursor: str | None = None,
    query_id: str | None = None,
    entity_type: EntityType | None = None,
    entity_ids: Sequence[UUID] | None = None,
    offset: int = 0,
    include_columns: bool = True,
) -> SearchPage:
    """Resume a search from `cursor`, else run the saved query `query_id`, else run `query`.

    `entity_type` rejects a cursor from another entity's search. `entity_ids` scopes the search; it is not saved
    with the query, so pass it again with every cursor. The query is saved only when a next page
    follows, as the next page cursor references it.

    `offset` skips ranked results, structured search only; a cursor already sets the start, so the two exclude
    each other.

    Raises:
        InvalidCursorError: When the cursor is malformed or belongs to another entity's search.
        QueryStateNotFoundError: When the saved query does not exist.
        ValueError: When none of query, cursor or query_id is given, the query is invalid, or `offset` is used
            with a cursor or a non-structured search.
    """
    if offset and cursor:
        raise ValueError("Page with either an offset or a cursor, not both")

    page_cursor = PageCursor.decode(cursor) if cursor else None
    query_state = await _load_query_state(session, query, page_cursor, query_id, entity_type)
    select_query = (
        query_state.query if include_columns else query_state.query.model_copy(update={"response_columns": []})
    )
    if offset and not Retriever.supports_offset(select_query):
        raise ValueError("An offset only works for structured search (filters without query text); page with a cursor")
    response = await engine.execute_search(
        select_query, session, page_cursor, query_state.query_embedding, entity_ids, offset
    )

    next_page_cursor = None
    if response.results:
        next_page_cursor = await encode_next_page_cursor(response, page_cursor, select_query, session)
    return SearchPage(response=response, next_page_cursor=next_page_cursor)

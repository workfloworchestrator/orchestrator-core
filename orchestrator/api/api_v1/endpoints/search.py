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

from fastapi import APIRouter, HTTPException, Query, status

from orchestrator.db import db
from orchestrator.schemas.search import (
    PageInfoSchema,
    PathsResponse,
    SearchResultsSchema,
)
from orchestrator.search.core.exceptions import InvalidCursorError
from orchestrator.search.core.types import EntityType, UIType
from orchestrator.search.filters.definitions import generate_definitions
from orchestrator.search.retrieval import execute_search
from orchestrator.search.retrieval.builder import build_paths_query, create_path_autocomplete_lquery, process_path_rows
from orchestrator.search.retrieval.pagination import (
    PaginationParams,
    create_next_page_cursor,
    process_pagination_cursor,
)
from orchestrator.search.retrieval.validation import is_lquery_syntactically_valid
from orchestrator.search.schemas.parameters import (
    ProcessSearchParameters,
    ProductSearchParameters,
    SearchParameters,
    SubscriptionSearchParameters,
    WorkflowSearchParameters,
)
from orchestrator.search.schemas.results import SearchResult, TypeDefinition

router = APIRouter()


async def _perform_search_and_fetch(
    search_params: SearchParameters,
    cursor: str | None = None,
    query_id: str | None = None,
) -> SearchResultsSchema[SearchResult]:
    """Execute search and return results.

    Args:
        search_params: Search parameters
        cursor: Pagination cursor
        query_id: Optional saved query ID to use for embedding retrieval

    Returns:
        Search results with entity_id, score, and matching_field.
    """
    # If query_id provided, retrieve saved embedding
    if query_id and not cursor:
        from uuid import UUID

        from orchestrator.db import SearchQueryTable

        try:
            query_uuid = UUID(query_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid query_id format: {query_id}",
            )

        search_query = db.session.query(SearchQueryTable).filter_by(query_id=query_uuid).first()
        if not search_query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Query {query_id} not found",
            )

        query_state = search_query.to_state()
        search_params = query_state.parameters
        pagination_params = PaginationParams(q_vec_override=query_state.query_embedding)
    else:
        try:
            pagination_params = await process_pagination_cursor(cursor, search_params)
        except InvalidCursorError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pagination cursor")

    search_response = await execute_search(search_params, db.session, pagination_params)
    if not search_response.results:
        return SearchResultsSchema(search_metadata=search_response.metadata)

    next_page_cursor = create_next_page_cursor(
        search_response.results, pagination_params, search_params.limit, search_params
    )
    has_next_page = next_page_cursor is not None
    page_info = PageInfoSchema(has_next_page=has_next_page, next_page_cursor=next_page_cursor)

    return SearchResultsSchema(
        data=search_response.results, page_info=page_info, search_metadata=search_response.metadata
    )


@router.post("/subscriptions", response_model=SearchResultsSchema[SearchResult])
async def search_subscriptions(
    search_params: SubscriptionSearchParameters,
    cursor: str | None = None,
    query_id: str | None = Query(None, description="Optional saved query ID for embedding retrieval"),
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(search_params, cursor, query_id)


@router.post("/workflows", response_model=SearchResultsSchema[SearchResult])
async def search_workflows(
    search_params: WorkflowSearchParameters,
    cursor: str | None = None,
    query_id: str | None = Query(None, description="Optional saved query ID for embedding retrieval"),
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(search_params, cursor, query_id)


@router.post("/products", response_model=SearchResultsSchema[SearchResult])
async def search_products(
    search_params: ProductSearchParameters,
    cursor: str | None = None,
    query_id: str | None = Query(None, description="Optional saved query ID for embedding retrieval"),
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(search_params, cursor, query_id)


@router.post("/processes", response_model=SearchResultsSchema[SearchResult])
async def search_processes(
    search_params: ProcessSearchParameters,
    cursor: str | None = None,
    query_id: str | None = Query(None, description="Optional saved query ID for embedding retrieval"),
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(search_params, cursor, query_id)


@router.get(
    "/paths",
    response_model=PathsResponse,
    response_model_exclude_none=True,
)
async def list_paths(
    prefix: str = Query("", min_length=0),
    q: str | None = Query(None, description="Query for path suggestions"),
    entity_type: EntityType = Query(EntityType.SUBSCRIPTION),
    limit: int = Query(10, ge=1, le=10),
) -> PathsResponse:

    if prefix:
        lquery_pattern = create_path_autocomplete_lquery(prefix)

        if not is_lquery_syntactically_valid(lquery_pattern, db.session):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Prefix '{prefix}' creates an invalid search pattern.",
            )
    stmt = build_paths_query(entity_type=entity_type, prefix=prefix, q=q)
    stmt = stmt.limit(limit)
    rows = db.session.execute(stmt).all()

    leaves, components = process_path_rows(rows)
    return PathsResponse(leaves=leaves, components=components)


@router.get(
    "/definitions",
    response_model=dict[UIType, TypeDefinition],
    response_model_exclude_none=True,
)
async def get_definitions() -> dict[UIType, TypeDefinition]:
    """Provide a static definition of operators and schemas for each UI type."""
    return generate_definitions()

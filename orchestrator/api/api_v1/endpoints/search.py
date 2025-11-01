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

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from orchestrator.db import db
from orchestrator.schemas.search import (
    ExportResponse,
    PageInfoSchema,
    PathsResponse,
    SearchResultsSchema,
)
from orchestrator.schemas.search_requests import SearchRequest
from orchestrator.search.core.exceptions import InvalidCursorError, QueryStateNotFoundError
from orchestrator.search.core.types import EntityType, UIType
from orchestrator.search.filters.definitions import TypeDefinition, generate_definitions
from orchestrator.search.query import QueryState, engine
from orchestrator.search.query.builder import build_paths_query, create_path_autocomplete_lquery, process_path_rows
from orchestrator.search.query.queries import ExportQuery, SelectQuery
from orchestrator.search.query.results import SearchResult
from orchestrator.search.query.validation import is_lquery_syntactically_valid
from orchestrator.search.retrieval.pagination import PageCursor, encode_next_page_cursor

router = APIRouter()
logger = structlog.get_logger(__name__)


async def _perform_search_and_fetch(
    entity_type: EntityType | None = None,
    request: SearchRequest | None = None,
    cursor: str | None = None,
    query_id: str | None = None,
) -> SearchResultsSchema[SearchResult]:
    """Execute search with optional pagination.

    Args:
        entity_type: Entity type to search
        request: Search request for new search
        cursor: Pagination cursor (loads saved query state)
        query_id: Saved query ID to retrieve and execute

    Returns:
        Search results with entity_id, score, and matching_field.
    """
    try:
        page_cursor: PageCursor | None = None
        query: SelectQuery

        if cursor:
            page_cursor = PageCursor.decode(cursor)
            query_state = QueryState.load_from_id(page_cursor.query_id, SelectQuery)
            query = query_state.query

        elif query_id:
            query_state = QueryState.load_from_id(query_id, SelectQuery)
            query = query_state.query

        elif request and entity_type:
            query = request.to_query(entity_type)
            query_state = QueryState(query=query, query_embedding=None)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either (request + entity_type), cursor, or query_id must be provided",
            )

        search_response = await engine.execute_search(query, db.session, page_cursor, query_state.query_embedding)
        if not search_response.results:
            return SearchResultsSchema(search_metadata=search_response.metadata)

        next_page_cursor = encode_next_page_cursor(search_response, page_cursor, query)
        has_next_page = next_page_cursor is not None
        page_info = PageInfoSchema(has_next_page=has_next_page, next_page_cursor=next_page_cursor)

        return SearchResultsSchema(
            data=search_response.results, page_info=page_info, search_metadata=search_response.metadata
        )
    except (InvalidCursorError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except QueryStateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post("/subscriptions", response_model=SearchResultsSchema[SearchResult])
async def search_subscriptions(
    request: SearchRequest,
    cursor: str | None = None,
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(EntityType.SUBSCRIPTION, request, cursor)


@router.post("/workflows", response_model=SearchResultsSchema[SearchResult])
async def search_workflows(
    request: SearchRequest,
    cursor: str | None = None,
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(EntityType.WORKFLOW, request, cursor)


@router.post("/products", response_model=SearchResultsSchema[SearchResult])
async def search_products(
    request: SearchRequest,
    cursor: str | None = None,
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(EntityType.PRODUCT, request, cursor)


@router.post("/processes", response_model=SearchResultsSchema[SearchResult])
async def search_processes(
    request: SearchRequest,
    cursor: str | None = None,
) -> SearchResultsSchema[SearchResult]:
    return await _perform_search_and_fetch(EntityType.PROCESS, request, cursor)


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


@router.get(
    "/queries/{query_id}",
    response_model=SearchResultsSchema[SearchResult],
    summary="Retrieve saved search results by query_id",
)
async def get_by_query_id(
    query_id: str,
    cursor: str | None = None,
) -> SearchResultsSchema[SearchResult]:
    """Retrieve and execute a saved search by query_id."""
    return await _perform_search_and_fetch(query_id=query_id, cursor=cursor)


@router.get(
    "/queries/{query_id}/export",
    summary="Export query results by query_id",
    response_model=ExportResponse,
)
async def export_by_query_id(query_id: str) -> ExportResponse:
    """Export search results using query_id.

    The query is retrieved from the database, re-executed, and results are returned
    as flattened records suitable for CSV download.

    Args:
        query_id: QueryTypes UUID

    Returns:
        ExportResponse containing 'page' with an array of flattened entity records.

    Raises:
        HTTPException: 404 if query not found, 400 if invalid data
    """
    try:
        # Load SelectQuery from the database (what gets saved during search)
        query_state = QueryState.load_from_id(query_id, SelectQuery)

        # Convert to ExportQuery with export-appropriate limit
        export_query = ExportQuery(
            entity_type=query_state.query.entity_type,
            filters=query_state.query.filters,
            query_text=query_state.query.query_text,
        )

        export_records = await engine.execute_export(export_query, db.session, query_state.query_embedding)
        return ExportResponse(page=export_records)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except QueryStateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing export: {str(e)}",
        )

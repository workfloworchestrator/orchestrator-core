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

"""GraphQL resolvers for search operations.

Mirrors the REST API endpoints in orchestrator.api.api_v1.endpoints.search,
delegating to the same service layer (engine, QueryState, definitions).
"""

from __future__ import annotations

from functools import lru_cache
from typing import cast
from uuid import UUID

import strawberry.scalars
import structlog
from graphql import GraphQLError

from orchestrator.db import SearchQueryTable, db
from orchestrator.graphql.schemas.search import (
    AggregationPairType,
    ComponentInfoType,
    CursorInfoType,
    ExportResponseType,
    GroupValuePairType,
    LeafInfoType,
    MatchingFieldType,
    PathsResponseType,
    QueryResultsResponseType,
    ResultRowType,
    SearchMetadataType,
    SearchPageInfoType,
    SearchResultsConnection,
    SearchResultType,
    TypeDefinitionType,
    ValueSchemaType,
    VisualizationKind,
    VisualizationType,
)
from orchestrator.graphql.search_inputs import SearchInput
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.search.core.exceptions import InvalidCursorError, QueryStateNotFoundError
from orchestrator.search.core.types import EntityType, FilterOp, SearchMetadata, UIType
from orchestrator.search.filters.definitions import ValueSchema, generate_definitions
from orchestrator.search.query import QueryState, engine
from orchestrator.search.query.builder import build_paths_query, create_path_autocomplete_lquery, process_path_rows
from orchestrator.search.query.queries import AggregateQuery, CountQuery, ExportQuery, QueryAdapter, SelectQuery
from orchestrator.search.query.results import MatchingField, QueryResultsResponse, ResultRow, SearchResult
from orchestrator.search.query.results import VisualizationType as DomainVisualizationType
from orchestrator.search.query.validation import is_lquery_syntactically_valid
from orchestrator.search.retrieval.pagination import PageCursor, encode_next_page_cursor

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper converters
# ---------------------------------------------------------------------------


def _matching_field_to_gql(mf: MatchingField) -> MatchingFieldType:
    """Convert a domain MatchingField to its GraphQL type."""
    return MatchingFieldType(
        text=mf.text,
        path=mf.path,
        highlight_indices=mf.highlight_indices,
    )


def _result_to_gql(result: SearchResult) -> SearchResultType:
    """Convert a domain SearchResult to its Strawberry GraphQL type."""
    return SearchResultType(
        entity_id=result.entity_id,
        entity_type=result.entity_type,
        entity_title=result.entity_title,
        score=result.score,
        perfect_match=result.perfect_match,
        matching_field=_matching_field_to_gql(result.matching_field) if result.matching_field else None,
        response_columns=cast(strawberry.scalars.JSON, result.response_columns) if result.response_columns else None,
    )


def _metadata_to_gql(metadata: SearchMetadata) -> SearchMetadataType:
    """Convert a domain SearchMetadata to its Strawberry GraphQL type."""
    return SearchMetadataType(
        search_type=metadata.search_type,
        description=metadata.description,
    )


def _build_search_results_connection(
    results: list[SearchResult],
    metadata: SearchMetadata,
    has_next_page: bool = False,
    next_page_cursor: str | None = None,
    total_items: int | None = None,
    start_cursor: int | None = None,
    end_cursor: int | None = None,
) -> SearchResultsConnection:
    """Assemble a SearchResultsConnection from domain objects."""
    page_info = SearchPageInfoType(
        has_next_page=has_next_page,
        next_page_cursor=next_page_cursor,
    )

    cursor_info = None
    if total_items is not None:
        cursor_info = CursorInfoType(
            total_items=total_items,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
        )

    return SearchResultsConnection(
        data=[_result_to_gql(r) for r in results],
        page_info=page_info,
        search_metadata=_metadata_to_gql(metadata),
        cursor=cursor_info,
    )


def _value_schema_to_gql(vs: ValueSchema, op: FilterOp) -> ValueSchemaType:
    """Convert a ValueSchema to its Strawberry GraphQL type."""
    fields = None
    if vs.fields:
        fields = [_value_schema_to_gql(child_vs, op) for child_vs in vs.fields.values()]
    return ValueSchemaType(
        operator=op,
        kind=vs.kind.value if isinstance(vs.kind, UIType) else str(vs.kind),
        fields=fields,
    )


def _domain_visualization_to_gql(viz: DomainVisualizationType) -> VisualizationType:
    """Convert a domain VisualizationType to its Strawberry GraphQL type."""
    return VisualizationType(type=VisualizationKind(viz.type))


def _result_row_to_gql(row: ResultRow) -> ResultRowType:
    """Convert a domain ResultRow to its Strawberry GraphQL type."""
    return ResultRowType(
        group_values=[GroupValuePairType(key=k, value=v) for k, v in row.group_values.items()],
        aggregations=[AggregationPairType(key=k, value=float(v)) for k, v in row.aggregations.items()],
    )


def _query_results_response_to_gql(resp: QueryResultsResponse) -> QueryResultsResponseType:
    """Convert a domain QueryResultsResponse to its Strawberry GraphQL type."""
    return QueryResultsResponseType(
        results=[_result_row_to_gql(r) for r in resp.results],
        total_results=resp.total_results,
        metadata=_metadata_to_gql(resp.metadata),
        visualization_type=_domain_visualization_to_gql(resp.visualization_type),
    )


# ---------------------------------------------------------------------------
# Shared search execution
# ---------------------------------------------------------------------------


async def _execute_search_and_paginate(
    query: SelectQuery,
    query_state: QueryState[SelectQuery],
    page_cursor: PageCursor | None,
) -> SearchResultsConnection:
    """Execute a search query and build a paginated connection result."""
    search_response = await engine.execute_search(query, db.session, page_cursor, query_state.query_embedding)
    next_page_cursor = encode_next_page_cursor(search_response, page_cursor, query) if search_response.results else None

    return _build_search_results_connection(
        results=search_response.results,
        metadata=search_response.metadata,
        has_next_page=next_page_cursor is not None,
        next_page_cursor=next_page_cursor,
        total_items=search_response.total_items,
        start_cursor=search_response.start_cursor,
        end_cursor=search_response.end_cursor,
    )


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


async def resolve_search(
    info: OrchestratorInfo,
    entity_type: EntityType,
    input: SearchInput,
    cursor: str | None = None,
    include_columns: bool = True,
) -> SearchResultsConnection:
    """Execute a search query, optionally with cursor-based pagination.

    Args:
        info: Strawberry resolver info.
        entity_type: The entity type to search.
        input: Search input containing query text, filters, limit, etc.
        cursor: Opaque pagination cursor from a previous page.
        include_columns: Whether to include response columns in results.
    """
    try:
        page_cursor: PageCursor | None = None
        query: SelectQuery

        if cursor:
            page_cursor = PageCursor.decode(cursor)
            query_state = QueryState.load_from_id(page_cursor.query_id, SelectQuery)
            query = query_state.query
        else:
            query = input.to_select_query(entity_type)
            query_state = QueryState(query=query, query_embedding=None)

        if not include_columns:
            query = query.model_copy(update={"response_columns": []})

        return await _execute_search_and_paginate(query, query_state, page_cursor)
    except (InvalidCursorError, ValueError) as e:
        raise GraphQLError(str(e), extensions={"code": "VALIDATION_ERROR"}) from e
    except QueryStateNotFoundError as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Search failed", error=str(e))
        raise GraphQLError(f"Search failed: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


async def resolve_search_paths(
    info: OrchestratorInfo,
    prefix: str = "",
    q: str | None = None,
    entity_type: EntityType = EntityType.SUBSCRIPTION,
    limit: int = 10,
) -> PathsResponseType:
    """Resolve path autocompletion suggestions.

    Mirrors the REST ``list_paths()`` endpoint.

    Args:
        info: Strawberry resolver info.
        prefix: Ltree prefix to filter paths.
        q: Optional text query for path suggestions.
        entity_type: Entity type scope.
        limit: Maximum number of results (1-10).

    Returns:
        PathsResponseType with leaves and components.
    """
    try:
        if prefix:
            lquery_pattern = create_path_autocomplete_lquery(prefix)
            if not is_lquery_syntactically_valid(lquery_pattern, db.session):
                raise GraphQLError(
                    f"Prefix '{prefix}' creates an invalid search pattern.",
                    extensions={"code": "VALIDATION_ERROR"},
                )

        stmt = build_paths_query(entity_type=entity_type, prefix=prefix, q=q)
        stmt = stmt.limit(max(1, min(limit, 10)))
        rows = db.session.execute(stmt).all()

        leaves, components = process_path_rows(rows)

        return PathsResponseType(
            leaves=[LeafInfoType(name=leaf.name, ui_types=leaf.ui_types, paths=leaf.paths) for leaf in leaves],
            components=[ComponentInfoType(name=comp.name, ui_types=comp.ui_types) for comp in components],
        )
    except GraphQLError:
        raise
    except Exception as e:
        logger.error("Path lookup failed", error=str(e))
        raise GraphQLError(f"Path lookup failed: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


@lru_cache(maxsize=1)
def _cached_definitions() -> list[TypeDefinitionType]:
    """Build and cache the static filter definitions (result is entirely derived from compiled code)."""
    return [
        TypeDefinitionType(
            ui_type=ui_type,
            operators=td.operators,
            value_schema=[_value_schema_to_gql(vs, op) for op, vs in td.value_schema.items()],
        )
        for ui_type, td in generate_definitions().items()
    ]


async def resolve_search_definitions(info: OrchestratorInfo) -> list[TypeDefinitionType]:
    """Resolve filter definitions for all UI types."""
    return _cached_definitions()


async def resolve_search_query_results(
    info: OrchestratorInfo,
    query_id: str,
) -> QueryResultsResponseType:
    """Fetch full query results by query_id, supporting select/count/aggregate.

    Mirrors the REST ``get_query_results()`` endpoint.

    Args:
        info: Strawberry resolver info.
        query_id: UUID string of the saved query.

    Returns:
        QueryResultsResponseType with tabular results and visualization hints.
    """
    try:
        query_uuid = UUID(query_id)
    except (ValueError, TypeError) as e:
        raise GraphQLError(f"Invalid query_id format: {query_id}", extensions={"code": "VALIDATION_ERROR"}) from e

    try:
        row = db.session.query(SearchQueryTable).filter_by(query_id=query_uuid).first()
        if not row:
            raise GraphQLError(f"Query {query_uuid} not found", extensions={"code": "NOT_FOUND"})

        query = QueryAdapter.validate_python(row.parameters)

        match query:
            case SelectQuery():
                embedding = list(row.query_embedding) if row.query_embedding is not None else None
                search_response = await engine.execute_search(query, db.session, query_embedding=embedding)
                result_rows = [
                    ResultRow(
                        group_values={
                            "entity_id": result.entity_id,
                            "title": result.entity_title,
                            "entity_type": result.entity_type.value,
                        },
                        aggregations={"score": result.score},
                    )
                    for result in search_response.results
                ]
                domain_resp = QueryResultsResponse(
                    results=result_rows,
                    total_results=len(result_rows),
                    metadata=search_response.metadata,
                )
                return _query_results_response_to_gql(domain_resp)

            case CountQuery() | AggregateQuery():
                domain_resp = await engine.execute_aggregation(query, db.session)
                return _query_results_response_to_gql(domain_resp)

            case _:
                raise GraphQLError(
                    f"Unsupported query type: {query.query_type}",
                    extensions={"code": "VALIDATION_ERROR"},
                )
    except GraphQLError:
        raise
    except QueryStateNotFoundError as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Failed to fetch query results", query_id=query_id, error=str(e))
        raise GraphQLError(f"Failed to fetch query results: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


async def resolve_search_query(
    info: OrchestratorInfo,
    query_id: str,
    cursor: str | None = None,
) -> SearchResultsConnection:
    """Retrieve and execute a saved search by query_id.

    Args:
        info: Strawberry resolver info.
        query_id: UUID string of the saved query.
        cursor: Optional pagination cursor.
    """
    try:
        page_cursor: PageCursor | None = None

        if cursor:
            page_cursor = PageCursor.decode(cursor)
            query_state = QueryState.load_from_id(page_cursor.query_id, SelectQuery)
        else:
            query_state = QueryState.load_from_id(query_id, SelectQuery)

        return await _execute_search_and_paginate(query_state.query, query_state, page_cursor)
    except (InvalidCursorError, ValueError) as e:
        raise GraphQLError(str(e), extensions={"code": "VALIDATION_ERROR"}) from e
    except QueryStateNotFoundError as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Search query failed", query_id=query_id, error=str(e))
        raise GraphQLError(f"Search query failed: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


async def resolve_search_query_export(
    info: OrchestratorInfo,
    query_id: str,
) -> ExportResponseType:
    """Export search results for a saved query.

    Mirrors the REST ``export_by_query_id()`` endpoint.

    Args:
        info: Strawberry resolver info.
        query_id: UUID string of the saved query.

    Returns:
        ExportResponseType with flattened entity records.
    """
    try:
        query_state = QueryState.load_from_id(query_id, SelectQuery)

        export_query = ExportQuery(
            entity_type=query_state.query.entity_type,
            filters=query_state.query.filters,
            query_text=query_state.query.query_text,
        )

        export_records = await engine.execute_export(export_query, db.session, query_state.query_embedding)
        return ExportResponseType(page=cast(list[strawberry.scalars.JSON], export_records))
    except ValueError as e:
        raise GraphQLError(str(e), extensions={"code": "VALIDATION_ERROR"}) from e
    except QueryStateNotFoundError as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Export failed", query_id=query_id, error=str(e))
        raise GraphQLError(f"Error executing export: {e}", extensions={"code": "INTERNAL_ERROR"}) from e

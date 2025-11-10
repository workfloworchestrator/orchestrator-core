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
from sqlalchemy.orm import Session

from orchestrator.search.core.embedding import QueryEmbedder
from orchestrator.search.core.types import SearchMetadata
from orchestrator.search.query.results import (
    AggregationResponse,
    SearchResponse,
    format_aggregation_response,
    format_search_response,
)
from orchestrator.search.retrieval.pagination import PageCursor
from orchestrator.search.retrieval.retrievers import Retriever

from .builder import build_aggregation_query, build_candidate_query, build_simple_count_query
from .export import fetch_export_data
from .queries import AggregateQuery, CountQuery, ExportQuery, SelectQuery

logger = structlog.get_logger(__name__)


async def _execute_search(
    query: SelectQuery | ExportQuery,
    db_session: Session,
    limit: int,
    cursor: PageCursor | None = None,
    query_embedding: list[float] | None = None,
) -> SearchResponse:
    """Internal implementation to execute search with specified query.

    Args:
        query: The SELECT or EXPORT query with vector, fuzzy, or filter criteria.
        db_session: The active SQLAlchemy session for executing the query.
        limit: Maximum number of results to return.
        cursor: Optional pagination cursor.
        query_embedding: Optional pre-computed query embedding to use instead of generating a new one.

    Returns:
        SearchResponse with results and embedding (for internal use).
    """
    if not query.vector_query and not query.filters and not query.fuzzy_term:
        logger.warning("No search criteria provided (vector_query, fuzzy_term, or filters).")
        return SearchResponse(results=[], metadata=SearchMetadata.empty())

    candidate_query = build_candidate_query(query)

    if query.vector_query and not query_embedding:
        query_embedding = await QueryEmbedder.generate_for_text_async(query.vector_query)

    retriever = Retriever.route(query, cursor, query_embedding)
    logger.debug("Using retriever", retriever_type=retriever.__class__.__name__)

    final_stmt = retriever.apply(candidate_query)
    final_stmt = final_stmt.limit(limit)
    logger.debug(final_stmt)
    result = db_session.execute(final_stmt).mappings().all()

    response = format_search_response(result, query, retriever.metadata)
    # Store embedding in response for agent to save to DB
    response.query_embedding = query_embedding
    return response


async def execute_search(
    query: SelectQuery,
    db_session: Session,
    cursor: PageCursor | None = None,
    query_embedding: list[float] | None = None,
) -> SearchResponse:
    """Execute a SELECT search query.

    This executes a SELECT action search using vector/fuzzy/filter search with ranking.

    Args:
        query: SelectQuery with search criteria
        db_session: Database session
        cursor: Optional pagination cursor
        query_embedding: Optional pre-computed embedding

    Returns:
        SearchResponse with ranked results
    """

    # Fetch one extra to determine if there is a next page
    fetch_limit = query.limit + 1 if query.limit > 0 else query.limit
    response = await _execute_search(query, db_session, fetch_limit, cursor, query_embedding)
    has_more = len(response.results) > query.limit and query.limit > 0

    # Trim to requested limit
    response.results = response.results[: query.limit]
    response.has_more = has_more

    return response


async def execute_export(
    query: ExportQuery,
    db_session: Session,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    """Execute a search and export flattened entity data.

    Args:
        query: ExportQuery with search criteria
        db_session: Database session
        query_embedding: Optional pre-computed embedding

    Returns:
        List of flattened entity records suitable for export.
    """
    search_response = await _execute_search(
        query=query,
        db_session=db_session,
        limit=query.limit,
        query_embedding=query_embedding,
    )

    entity_ids = [res.entity_id for res in search_response.results]
    return fetch_export_data(query.entity_type, entity_ids)


async def execute_aggregation(
    query: CountQuery | AggregateQuery,
    db_session: Session,
) -> AggregationResponse:
    """Execute aggregation query and return formatted results.

    Args:
        query: CountQuery or AggregateQuery
        db_session: Database session

    Returns:
        AggregationResponse with results and metadata
    """
    candidate_query = build_candidate_query(query)

    if isinstance(query, CountQuery) and not query.group_by and not query.temporal_group_by:
        # Simple count without grouping
        agg_query = build_simple_count_query(candidate_query)
        group_column_names: list[str] = []
    else:
        # Grouped aggregation - needs pivoting
        agg_query, group_column_names = build_aggregation_query(query, candidate_query)

    logger.debug("Executing aggregation query", sql=str(agg_query))

    result_rows = db_session.execute(agg_query).mappings().all()

    return format_aggregation_response(result_rows, group_column_names, query)

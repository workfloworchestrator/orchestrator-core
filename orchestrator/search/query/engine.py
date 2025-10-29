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
from orchestrator.search.core.types import ActionType, SearchMetadata
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
from .models import BaseQuery
from .state import QueryState

logger = structlog.get_logger(__name__)


async def _execute_search_internal(
    query: BaseQuery,
    db_session: Session,
    limit: int,
    cursor: PageCursor | None = None,
    query_embedding: list[float] | None = None,
) -> SearchResponse:
    """Internal function to execute search with specified query.

    Args:
        query: The query plan with vector, fuzzy, or filter criteria.
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
    query: BaseQuery,
    db_session: Session,
    cursor: PageCursor | None = None,
    query_embedding: list[float] | None = None,
) -> SearchResponse:
    """Execute a SELECT search query.

    This executes a SELECT action search using vector/fuzzy/filter search with ranking.

    Args:
        query: Query plan with SELECT action
        db_session: Database session
        cursor: Optional pagination cursor
        query_embedding: Optional pre-computed embedding

    Returns:
        SearchResponse with ranked results
    """
    if query.action != ActionType.SELECT:
        raise ValueError(
            f"execute_search only handles SELECT actions. "
            f"Got '{query.action}'. Use execute_aggregation for COUNT/AGGREGATE."
        )

    return await _execute_search_internal(query, db_session, query.limit, cursor, query_embedding)


async def execute_search_for_export(
    query_state: QueryState,
    db_session: Session,
) -> list[dict]:
    """Execute a search for export and fetch flattened entity data.

    Args:
        query_state: Query state containing parameters and query_embedding.
        db_session: The active SQLAlchemy session for executing the query.

    Returns:
        List of flattened entity records suitable for export.
    """
    search_response = await _execute_search_internal(
        query=query_state.parameters,
        db_session=db_session,
        limit=query_state.parameters.export_limit,
        query_embedding=query_state.query_embedding,
    )

    entity_ids = [res.entity_id for res in search_response.results]
    return fetch_export_data(query_state.parameters.entity_type, entity_ids)


async def execute_aggregation(
    query: BaseQuery,
    db_session: Session,
) -> AggregationResponse:
    """Execute aggregation query and return formatted results.

    Args:
        query: Query plan with COUNT or AGGREGATE action
        db_session: Database session

    Returns:
        AggregationResponse with results and metadata
    """
    if query.action not in (ActionType.COUNT, ActionType.AGGREGATE):
        raise ValueError(
            f"execute_aggregation only handles COUNT and AGGREGATE actions. "
            f"Got '{query.action}'. Use execute_search for SELECT."
        )

    candidate_query = build_candidate_query(query)

    if query.action == ActionType.COUNT and not query.group_by and not query.temporal_group_by:
        # Simple count without grouping
        agg_query = build_simple_count_query(candidate_query)
        group_column_names: list[str] = []
    else:
        # Grouped aggregation - needs pivoting
        agg_query, group_column_names = build_aggregation_query(query, candidate_query)

    logger.debug("Executing aggregation query", sql=str(agg_query))

    result_rows = db_session.execute(agg_query).mappings().all()

    return format_aggregation_response(result_rows, group_column_names, query)

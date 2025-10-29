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

from .builder import build_aggregation_query, build_candidate_query
from .models import BaseQuery
from .state import QueryState

logger = structlog.get_logger(__name__)


async def _execute_search_internal(
    search_params: BaseQuery,
    db_session: Session,
    limit: int,
    cursor: PageCursor | None = None,
    query_embedding: list[float] | None = None,
) -> SearchResponse:
    """Internal function to execute search with specified parameters.

    Args:
        search_params: The search parameters specifying vector, fuzzy, or filter criteria.
        db_session: The active SQLAlchemy session for executing the query.
        limit: Maximum number of results to return.
        cursor: Optional pagination cursor.
        query_embedding: Optional pre-computed query embedding to use instead of generating a new one.

    Returns:
        SearchResponse with results and embedding (for internal use).
    """
    if not search_params.vector_query and not search_params.filters and not search_params.fuzzy_term:
        logger.warning("No search criteria provided (vector_query, fuzzy_term, or filters).")
        return SearchResponse(results=[], metadata=SearchMetadata.empty())

    candidate_query = build_candidate_query(search_params)

    if search_params.vector_query and not query_embedding:

        query_embedding = await QueryEmbedder.generate_for_text_async(search_params.vector_query)

    from orchestrator.search.retrieval.retrievers import Retriever

    retriever = await Retriever.route(search_params, cursor, query_embedding)
    logger.debug("Using retriever", retriever_type=retriever.__class__.__name__)

    final_stmt = retriever.apply(candidate_query)
    final_stmt = final_stmt.limit(limit)
    logger.debug(final_stmt)
    result = db_session.execute(final_stmt).mappings().all()

    response = format_search_response(result, search_params, retriever.metadata)
    # Store embedding in response for agent to save to DB
    response.query_embedding = query_embedding
    return response


async def execute_search(
    search_params: BaseQuery,
    db_session: Session,
    cursor: PageCursor | None = None,
    query_embedding: list[float] | None = None,
) -> SearchResponse:
    """Execute a SELECT search query.

    This executes a SELECT action search using vector/fuzzy/filter search with ranking.

    Args:
        search_params: Search parameters with SELECT action
        db_session: Database session
        cursor: Optional pagination cursor
        query_embedding: Optional pre-computed embedding

    Returns:
        SearchResponse with ranked results
    """
    if search_params.action != ActionType.SELECT:
        raise ValueError(
            f"execute_search only handles SELECT actions. "
            f"Got '{search_params.action}'. Use execute_aggregation for COUNT/AGGREGATE."
        )

    return await _execute_search_internal(search_params, db_session, search_params.limit, cursor, query_embedding)


async def execute_search_for_export(
    query_state: QueryState,
    db_session: Session,
) -> list[dict]:
    """Execute a search for export and fetch flattened entity data.

    Args:
        query_state: QueryTypes state containing parameters and query_embedding.
        db_session: The active SQLAlchemy session for executing the query.

    Returns:
        List of flattened entity records suitable for export.
    """
    from orchestrator.search.query.export import fetch_export_data

    search_response = await _execute_search_internal(
        search_params=query_state.parameters,
        db_session=db_session,
        limit=query_state.parameters.export_limit,
        query_embedding=query_state.query_embedding,
    )

    entity_ids = [res.entity_id for res in search_response.results]
    return fetch_export_data(query_state.parameters.entity_type, entity_ids)


async def execute_aggregation(
    params: BaseQuery,
    db_session: Session,
) -> AggregationResponse:
    """Execute aggregation query and return formatted results.

    Args:
        params: Search parameters with aggregation settings
        db_session: Database session
        base_query: Optional base candidate query with filters. If None, will be built automatically.

    Returns:
        AggregationResponse with results and metadata
    """
    candidate_query = build_candidate_query(params)

    if params.action == ActionType.COUNT and not params.group_by and not params.temporal_group_by:
        # Simple count without grouping
        from sqlalchemy import func, select

        agg_query = select(func.count(func.distinct(candidate_query.c.entity_id)).label("total_count")).select_from(
            candidate_query.subquery()
        )
        group_column_names: list[str] = []
    else:
        # Grouped aggregation - needs pivoting
        agg_query, group_column_names = build_aggregation_query(params, candidate_query)

    logger.debug("Executing aggregation query", sql=str(agg_query))

    result_rows = db_session.execute(agg_query).mappings().all()

    return format_aggregation_response(result_rows, group_column_names, params)

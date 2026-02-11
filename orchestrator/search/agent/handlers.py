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

"""Handlers for search and aggregation execution with persistence."""

from uuid import UUID

import structlog

from orchestrator.db import SearchQueryTable
from orchestrator.db.database import WrappedSession
from orchestrator.search.query import engine
from orchestrator.search.query.queries import AggregateQuery, CountQuery, SelectQuery
from orchestrator.search.query.results import AggregationResponse, SearchResponse
from orchestrator.search.query.state import QueryState

logger = structlog.get_logger(__name__)


async def execute_search_with_persistence(
    query: SelectQuery,
    db_session: WrappedSession,
    run_id: UUID | None,
) -> tuple[SearchResponse, UUID, UUID]:
    """Execute search, persist to DB, return response and IDs.

    Args:
        query: SelectQuery for search operation
        db_session: Database session
        run_id: Existing run ID or None to create new one

    Returns:
        Tuple of (search_response, run_id, query_id)
    """
    # run_id must be provided when called from graph agent (endpoint creates the run)
    if run_id is None:
        raise ValueError("run_id is required - agent run must be created by endpoint with thread_id")

    # Execute search
    search_response = await engine.execute_search(query, db_session)

    # Save to database
    query_embedding = search_response.query_embedding
    query_state = QueryState(query=query, query_embedding=query_embedding)
    query_number = db_session.query(SearchQueryTable).filter_by(run_id=run_id).count() + 1
    search_query = SearchQueryTable.from_state(
        state=query_state,
        run_id=run_id,
        query_number=query_number,
    )
    db_session.add(search_query)
    db_session.commit()
    db_session.expire_all()

    logger.debug("Saved search query", query_id=str(search_query.query_id), query_number=query_number)
    return search_response, run_id, search_query.query_id


async def execute_aggregation_with_persistence(
    query: CountQuery | AggregateQuery,
    db_session: WrappedSession,
    run_id: UUID | None,
) -> tuple[AggregationResponse, UUID, UUID]:
    """Execute aggregation, persist to DB, return response and IDs.

    Args:
        query: CountQuery or AggregateQuery for aggregation operations
        db_session: Database session
        run_id: Existing run ID or None to create new one

    Returns:
        Tuple of (aggregation_response, run_id, query_id)
    """
    # run_id must be provided when called from graph agent (endpoint creates the run)
    if run_id is None:
        raise ValueError("run_id is required - agent run must be created by endpoint with thread_id")

    # Execute aggregation
    aggregation_response = await engine.execute_aggregation(query, db_session)

    # Save to database
    query_state = QueryState(query=query, query_embedding=None)
    query_number = db_session.query(SearchQueryTable).filter_by(run_id=run_id).count() + 1
    search_query = SearchQueryTable.from_state(
        state=query_state,
        run_id=run_id,
        query_number=query_number,
    )
    db_session.add(search_query)
    db_session.commit()
    db_session.expire_all()

    logger.debug("Saved aggregation query", query_id=str(search_query.query_id), query_number=query_number)

    return aggregation_response, run_id, search_query.query_id

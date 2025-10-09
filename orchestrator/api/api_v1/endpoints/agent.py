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

from functools import cache
from structlog import get_logger
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic_ai.ag_ui import StateDeps, handle_ag_ui_request
from pydantic_ai.agent import Agent
from starlette.responses import Response

from orchestrator.db import AgentQueryTable, db
from orchestrator.llm_settings import llm_settings
from orchestrator.search.agent import build_agent_instance
from orchestrator.search.agent.state import SearchState
from orchestrator.search.retrieval import execute_search_for_export

router = APIRouter()
logger = get_logger(__name__)


@cache
def get_agent() -> Agent[StateDeps[SearchState], str]:
    """Dependency to provide the agent instance.

    The agent is built once and cached for the lifetime of the application.
    """
    return build_agent_instance(llm_settings.AGENT_MODEL, agent_tools=None)


@router.post("/")
async def agent_conversation(
    request: Request,
    agent: Annotated[Agent[StateDeps[SearchState], str], Depends(get_agent)],
) -> Response:
    """Agent conversation endpoint using pydantic-ai ag_ui protocol.

    This endpoint handles the interactive agent conversation for search.
    """
    initial_state = SearchState()
    return await handle_ag_ui_request(agent, request, deps=StateDeps(initial_state))


@router.get(
    "/runs/{run_id}/queries/{query_id}/export",
    summary="Export query results by run_id and query_id",
    response_model=dict[str, Any],
)
async def export_by_query_id(run_id: str, query_id: str) -> dict[str, Any]:
    """Export search results using run_id and query_id.

    The query is retrieved from the database, re-executed, and results are returned
    as flattened records suitable for CSV download.

    Args:
        run_id: Agent run UUID
        query_id: Query UUID

    Returns:
        Dictionary containing 'page' with an array of flattened entity records.
        Each record contains snake_case field names from the database with nested
        relationships flattened (e.g., product_name instead of product.name).

    Raises:
        HTTPException: 404 if query not found, 400 if invalid data
    """
    from uuid import UUID

    from orchestrator.search.export import fetch_export_data

    try:
        query_uuid = UUID(query_id)
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run_id or query_id format",
        )

    agent_query = db.session.query(AgentQueryTable).filter_by(query_id=query_uuid, run_id=run_uuid).first()

    if not agent_query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Query {query_id} not found in run {run_id}",
        )
    try:
        from orchestrator.search.retrieval.pagination import PaginationParams

        # Get the full query state including the embedding that was used
        query_state = agent_query.get_state()

        # Create pagination params with the saved embedding to ensure consistent results
        pagination_params = PaginationParams(
            q_vec_override=query_state.query_embedding.tolist() if query_state.query_embedding is not None else None
        )

        search_response = await execute_search_for_export(query_state.parameters, db.session, pagination_params)
        entity_ids = [res.entity_id for res in search_response.results]

        export_records = fetch_export_data(query_state.parameters.entity_type, entity_ids)

        return {"page": export_records}

    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing export: {str(e)}",
        )

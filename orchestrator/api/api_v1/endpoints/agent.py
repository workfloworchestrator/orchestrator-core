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
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic_ai.ag_ui import StateDeps, handle_ag_ui_request
from pydantic_ai.agent import Agent
from starlette.responses import Response
from structlog import get_logger

from orchestrator.db import db
from orchestrator.llm_settings import llm_settings
from orchestrator.schemas.search import ExportResponse
from orchestrator.search.agent import build_agent_instance
from orchestrator.search.agent.state import SearchState
from orchestrator.search.core.exceptions import QueryStateNotFoundError
from orchestrator.search.retrieval import SearchQueryState, execute_search_for_export

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
    "/queries/{query_id}/export",
    summary="Export query results by query_id",
    response_model=ExportResponse,
)
async def export_by_query_id(query_id: str) -> ExportResponse:
    """Export search results using query_id.

    The query is retrieved from the database, re-executed, and results are returned
    as flattened records suitable for CSV download.

    Args:
        query_id: Query UUID

    Returns:
        ExportResponse containing 'page' with an array of flattened entity records.

    Raises:
        HTTPException: 404 if query not found, 400 if invalid data
    """
    try:
        query_state = SearchQueryState.load_from_id(query_id)
        export_records = await execute_search_for_export(query_state, db.session)
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

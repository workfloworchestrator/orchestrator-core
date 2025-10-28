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

from fastapi import APIRouter, Depends, Request
from pydantic_ai.ag_ui import StateDeps, handle_ag_ui_request
from pydantic_ai.agent import Agent
from starlette.responses import Response
from structlog import get_logger

from orchestrator.search.agent import build_agent_instance
from orchestrator.search.agent.state import SearchState

router = APIRouter()
logger = get_logger(__name__)


@cache
def get_agent(request: Request) -> Agent[StateDeps[SearchState], str]:
    """Dependency to provide the agent instance.

    The agent is built once and cached for the lifetime of the application.
    """
    return build_agent_instance(request.app.agent_model)


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

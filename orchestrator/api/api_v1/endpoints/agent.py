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
from typing import Annotated, AsyncGenerator

from ag_ui.core import RunAgentInput
from anyio import create_memory_object_stream, create_task_group
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from pydantic_ai.ag_ui import SSE_CONTENT_TYPE, StateDeps, run_ag_ui
from starlette.responses import Response, StreamingResponse
from structlog import get_logger

from orchestrator.search.agent.agent import GraphAgentAdapter, build_agent_instance
from orchestrator.search.agent.schemas import GraphStructure
from orchestrator.search.agent.state import SearchState

router = APIRouter()
logger = get_logger(__name__)


@cache
def get_agent(request: Request) -> GraphAgentAdapter:
    """Dependency to provide the agent instance.

    The agent is built once and cached for the lifetime of the application.
    """
    model = request.app.agent_model

    logger.debug("Building graph agent instance", model=model)
    return build_agent_instance(model)


@router.post("/")
async def agent_conversation(
    request: Request,
    agent: Annotated[GraphAgentAdapter, Depends(get_agent)],
) -> Response:
    """Agent conversation endpoint using pydantic-ai ag_ui protocol.

    This endpoint handles the interactive agent conversation for search.
    Uses manual stream management to allow custom graph events to be injected.
    """

    # Parse the request body to get RunAgentInput
    try:
        body = await request.json()
        run_input = RunAgentInput(**body)
    except ValidationError as e:
        logger.error("Invalid request body", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    # Create memory stream for events
    send_stream, receive_stream = create_memory_object_stream[str]()

    async def run_agent_task() -> None:
        """Run the agent and send events to the stream."""
        event_iterator = run_ag_ui(agent, run_input=run_input, deps=StateDeps(SearchState()))

        async for event in event_iterator:
            # First, check if there are any graph events to inject
            if hasattr(agent, "_current_graph_events"):
                while agent._current_graph_events:
                    custom_event = agent._current_graph_events.popleft()
                    await send_stream.send(custom_event)

            # Then send the regular event
            await send_stream.send(event)

    async def stream_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the memory stream."""
        async with create_task_group() as tg:
            # Start agent execution in background
            tg.start_soon(run_agent_task)

            # Stream events as they arrive
            async with receive_stream:
                async for event in receive_stream:
                    yield event

    return StreamingResponse(stream_generator(), media_type=SSE_CONTENT_TYPE)


@router.get("/graph")
async def get_graph_structure(
    request: Request,
    agent: Annotated[GraphAgentAdapter, Depends(get_agent)],
) -> GraphStructure:
    """Get the agent graph structure for visualization.

    Returns structured graph data (nodes and edges) that the frontend can use to:
    - Visualize the graph structure
    - Highlight nodes based on events received during execution

    Args:
        request: FastAPI request object
        agent: The agent instance (injected by FastAPI dependency)

    Returns:
        GraphStructure with nodes, edges, and start_node
    """
    logger.info("Retrieving graph structure")
    return agent.get_graph_structure()

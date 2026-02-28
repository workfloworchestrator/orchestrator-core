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

"""MCP (Model Context Protocol) adapter for the search agent.

MCPWorker owns the agent lifecycle and stream consumption — parallel to
AGUIWorker and A2AWorker.  It consumes ``agent.run_stream_events()`` to
collect ToolArtifact results and the final LLM output, then returns a
combined result string.

The FastMCP tool handlers are thin wrappers that delegate to the worker.

Unlike AG-UI (streaming SSE to a frontend) or A2A (task lifecycle with
broker/storage), the MCP adapter is **stateless** — each tool call is
independent with no session or memory between calls.
"""

from __future__ import annotations

import uuid
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart
from pydantic_ai.run import AgentRunResultEvent

from orchestrator.db import db
from orchestrator.db.models import AgentRunTable
from orchestrator.search.agent.agent import AgentAdapter
from orchestrator.search.agent.artifacts import ToolArtifact
from orchestrator.search.agent.state import SearchState, TaskAction
from orchestrator.search.core.types import EntityType

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = structlog.get_logger(__name__)


class MCPWorker:
    """Orchestrates MCP tool execution: state setup, stream consumption, result assembly.

    Parallel to AGUIWorker and A2AWorker — owns the agent reference and the
    full tool-call lifecycle so the FastMCP handlers stay thin.
    """

    def __init__(self, agent: AgentAdapter) -> None:
        self.agent = agent

    async def run_skill(self, query: str, target_action: TaskAction | None = None) -> str:
        """Create state, consume the agent stream, and return a result string.

        Same stream-consumption pattern as ``A2AWorker._consume_stream()`` —
        collects ToolArtifact results and the final LLM output.
        """
        deps = StateDeps(SearchState(user_input=query))

        deps.state.run_id = uuid.uuid4()
        agent_run = AgentRunTable(run_id=deps.state.run_id, thread_id=str(uuid.uuid4()), agent_type="mcp")
        db.session.add(agent_run)
        db.session.commit()

        logger.debug("MCPWorker: Starting skill execution", target_action=target_action, query=query[:100])

        try:
            artifact_results: list[ToolReturnPart] = []
            final_output = ""

            async for event in self.agent.run_stream_events(deps=deps, target_action=target_action):
                if isinstance(event, FunctionToolResultEvent):
                    result = event.result
                    if isinstance(result, ToolReturnPart) and isinstance(result.metadata, ToolArtifact):
                        artifact_results.append(result)

                if isinstance(event, AgentRunResultEvent):
                    final_output = str(event.result.output)
        except Exception:
            logger.exception("MCPWorker: Skill execution failed", query=query[:100])
            raise

        if artifact_results:
            return "\n\n".join(part.model_response_str() for part in artifact_results)

        return final_output or "No results"



mcp = FastMCP(
    name="WFO Search Agent",
    instructions="Search, filter and aggregate orchestration data",
    stateless_http=True,
)

# Module-level worker reference, set by create_mcp_app().
_worker: MCPWorker | None = None


def _get_worker() -> MCPWorker:
    if _worker is None:
        raise RuntimeError("MCP adapter not initialized — call create_mcp_app() first")
    return _worker


@mcp.tool()
async def search(query: str) -> str:
    """Find subscriptions, products, workflows, or processes.

    Describe what you're looking for in natural language.
    Examples: "active subscriptions", "failed workflows from last week"
    """
    return await _get_worker().run_skill(query, TaskAction.SEARCH)


@mcp.tool()
async def aggregate(query: str) -> str:
    """Count, sum, or average data with grouping.

    Describe what aggregation you need.
    Examples: "count subscriptions by product", "average workflow duration by status"
    """
    return await _get_worker().run_skill(query, TaskAction.AGGREGATION)


@mcp.tool()
async def get_entity_details(entity_type: EntityType, entity_id: uuid.UUID) -> str:
    """Fetch full details for a specific entity.

    Args:
        entity_type: The type of entity (SUBSCRIPTION, PRODUCT, WORKFLOW, PROCESS)
        entity_id: The UUID of the entity
    """
    query = f"Get details for {entity_type.value} {entity_id}"
    return await _get_worker().run_skill(query, TaskAction.RESULT_ACTIONS)


@mcp.tool()
async def ask(query: str) -> str:
    """Ask any question about the orchestration system.

    The agent will determine the best approach — search, aggregate, or answer directly.
    """
    return await _get_worker().run_skill(query, target_action=None)



def create_mcp_app(agent: AgentAdapter) -> Starlette:
    """Create MCP Starlette app to mount as sub-app.

    Args:
        agent: The AgentAdapter instance to expose via MCP.

    Returns:
        A Starlette application serving the MCP streamable HTTP transport.
    """
    global _worker
    _worker = MCPWorker(agent)
    return mcp.streamable_http_app()


async def start_mcp() -> AsyncExitStack:
    """Start the MCP session manager.

    Sub-app lifespans don't run when mounted, so the host application
    must call this during its own startup.  Returns an AsyncExitStack
    that must be closed during shutdown to cleanly stop the session manager.

    Must be called after ``create_mcp_app()`` (which triggers lazy
    initialisation of the session manager via ``streamable_http_app()``).
    """
    stack = AsyncExitStack()
    await stack.__aenter__()
    await stack.enter_async_context(mcp.session_manager.run())
    return stack

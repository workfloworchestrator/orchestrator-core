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

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic_ai.ag_ui import StateDeps

from orchestrator.db import db
from orchestrator.db.models import AgentRunTable
from orchestrator.search.agent.adapters.stream import collect_stream_output
from orchestrator.search.agent.agent import AgentAdapter
from orchestrator.search.agent.state import SearchState, TaskAction
from orchestrator.search.core.types import EntityType

logger = structlog.get_logger(__name__)


class MCPWorker:
    """Orchestrates MCP tool execution: state setup, stream consumption, result assembly.

    Parallel to AGUIWorker and A2AWorker — owns the agent reference and the
    full tool-call lifecycle so the FastMCP handlers stay thin.
    """

    def __init__(self, agent: AgentAdapter) -> None:
        self.agent = agent

    async def run_skill(self, query: str, target_action: TaskAction | None = None) -> str:
        """Create state, consume the agent stream, and return a result string."""
        deps = StateDeps(SearchState(user_input=query))

        deps.state.run_id = uuid.uuid4()
        agent_run = AgentRunTable(run_id=deps.state.run_id, thread_id=str(uuid.uuid4()), agent_type="mcp")
        db.session.add(agent_run)
        db.session.commit()

        logger.debug("MCPWorker: Starting skill execution", target_action=target_action, query=query[:100])

        try:
            event_stream = self.agent.run_stream_events(deps=deps, target_action=target_action)
            return await collect_stream_output(event_stream)
        except Exception:
            logger.exception("MCPWorker: Skill execution failed", query=query[:100])
            raise


class MCPApp:
    """MCP adapter app: FastMCP server, worker, tools, and lifecycle.

    Bundles the Starlette sub-app with the session manager lifecycle so the
    host can ``async with mcp_app`` symmetrically with A2AApp.  Tool handlers
    close over ``self.worker`` — no module-level global needed.
    """

    def __init__(self, agent: AgentAdapter) -> None:
        self.agent = agent
        self.worker = MCPWorker(agent)
        self._stack: AsyncExitStack

        self.server = FastMCP(
            name="WFO Search Agent",
            instructions="Search, filter and aggregate orchestration data",
            stateless_http=True,
        )
        self._register_tools()
        self.app = self.server.streamable_http_app()

    def _register_tools(self) -> None:
        worker = self.worker

        @self.server.tool()  # type: ignore[misc]
        async def search(query: str) -> str:
            """Find subscriptions, products, workflows, or processes.

            Describe what you're looking for in natural language.
            Examples: "active subscriptions", "failed workflows from last week"
            """
            return await worker.run_skill(query, TaskAction.SEARCH)

        @self.server.tool()  # type: ignore[misc]
        async def aggregate(query: str) -> str:
            """Count, sum, or average data with grouping.

            Describe what aggregation you need.
            Examples: "count subscriptions by product", "average workflow duration by status"
            """
            return await worker.run_skill(query, TaskAction.AGGREGATION)

        @self.server.tool()  # type: ignore[misc]
        async def get_entity_details(entity_type: EntityType, entity_id: uuid.UUID) -> str:
            """Fetch full details for a specific entity.

            Args:
                entity_type: The type of entity (SUBSCRIPTION, PRODUCT, WORKFLOW, PROCESS)
                entity_id: The UUID of the entity
            """
            query = f"Get details for {entity_type.value} {entity_id}"
            return await worker.run_skill(query, TaskAction.RESULT_ACTIONS)

        @self.server.tool()  # type: ignore[misc]
        async def ask(query: str) -> str:
            """Ask any question about the orchestration system.

            The agent will determine the best approach — search, aggregate, or answer directly.
            """
            return await worker.run_skill(query, target_action=None)

    async def __aenter__(self) -> MCPApp:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        await self._stack.enter_async_context(self.server.session_manager.run())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        await self._stack.__aexit__(exc_type, exc_val, exc_tb)

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


from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

import structlog
from ag_ui.core import BaseEvent
from pydantic_ai import Agent
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import AgentStreamEvent
from pydantic_graph import BaseNode, End, GraphRunContext

from orchestrator.search.agent.graph_events import (
    GraphNodeEnterEvent,
    GraphNodeEnterValue,
    GraphNodeExitEvent,
    GraphNodeExitValue,
)
from orchestrator.search.agent.prompts import (
    get_execution_prompt,
    get_filter_building_prompt,
    get_query_analysis_prompt,
    get_response_prompt,
)
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.tools import (
    execution_toolset,
    filter_building_toolset,
    query_analysis_toolset,
    search_toolset,
)

logger = structlog.get_logger(__name__)


def _current_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    from time import time_ns

    return time_ns() // 1_000_000


NODE_CONFIG = {
    "QueryAnalysisNode": {
        "prompt_fn": get_query_analysis_prompt,
        "toolsets": [query_analysis_toolset],
    },
    "FilterBuildingNode": {
        "prompt_fn": get_filter_building_prompt,
        "toolsets": [filter_building_toolset],
    },
    "ExecutionNode": {
        "prompt_fn": get_execution_prompt,
        "toolsets": [execution_toolset],
    },
    "ResultProcessingNode": {
        "prompt_fn": lambda _: "Process results: call fetch_entity_details or prepare_export if needed.",
        "toolsets": [search_toolset],
    },
    "ResponseNode": {
        "prompt_fn": get_response_prompt,
        "toolsets": [],
    },
}


@dataclass
class BaseGraphNode:
    """Base class for all graph nodes with common fields and streaming logic."""

    search_agent: Agent[StateDeps["SearchState"], str]
    event_emitter: Callable[[BaseEvent], Awaitable[None]] | None = None

    @property
    def node_name(self) -> str:
        """Get the name of this node for event emission."""
        return self.__class__.__name__

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str | None:
        """Get the prompt for the skill agent from NODE_CONFIG."""
        config = NODE_CONFIG.get(self.node_name)
        if not config:
            return None
        prompt_fn = config["prompt_fn"]
        if not prompt_fn:
            return None

        return prompt_fn(ctx.state)

    @property
    def toolsets(self) -> list[Any]:
        """Get the toolsets for this node from NODE_CONFIG."""
        config = NODE_CONFIG.get(self.node_name)
        if not config:
            return []
        return config["toolsets"]

    async def event_generator(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AgentStreamEvent]:
        """Generate events from the search agent as they happen."""
        # Emit GRAPH_NODE_ENTER event at the start
        if hasattr(self, "event_emitter") and self.event_emitter:
            value: GraphNodeEnterValue = {"node": self.node_name, "step_type": "graph_node"}
            graph_event = GraphNodeEnterEvent(timestamp=_current_timestamp_ms(), value=value)
            await self.event_emitter(graph_event)

        prompt = self.get_prompt(ctx)
        if prompt is None:
            return  # No prompt means no agent call

        state_deps = StateDeps(ctx.state)
        toolsets = self.toolsets

        # Start with clean message history to avoid empty/null content messages across nodes
        async with self.search_agent.iter(
            user_prompt=prompt, deps=state_deps, toolsets=toolsets, message_history=[]
        ) as agent_run:
            async for agent_node in agent_run:
                if Agent.is_model_request_node(agent_node):
                    async with agent_node.stream(agent_run.ctx) as event_stream:
                        async for stream_event in event_stream:
                            yield stream_event

    async def _emit_exit(self, to_node_name: str | None, decision: str | None = None) -> None:
        """Helper to emit EXIT event with transition info.

        Args:
            to_node_name: Name of the node to transition to (None for final node)
            decision: Human-readable reason for the transition (optional)
        """
        if not hasattr(self, "event_emitter") or not self.event_emitter:
            return

        exit_value: GraphNodeExitValue = {
            "node": self.node_name,
            "next_node": to_node_name,
            "decision": decision,
        }
        await self.event_emitter(GraphNodeExitEvent(timestamp=_current_timestamp_ms(), value=exit_value))

    @asynccontextmanager
    async def stream(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AsyncIterator[AgentStreamEvent]]:
        yield self.event_generator(ctx)


@dataclass
class QueryAnalysisNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    user_input: str = field(kw_only=True)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> FilterBuildingNode:
        """Route to next node after query analysis.

        The agent execution happened during stream(), so ctx.state is already updated.
        Always route to FilterBuildingNode - the agent there will decide if filters are needed.

        Returns:
            FilterBuildingNode - always route to filter building
        """
        logger.debug(
            f"{self.node_name}: Analysis complete",
            action=ctx.state.action,
            has_query=ctx.state.query is not None,
        )

        next_node = FilterBuildingNode(search_agent=self.search_agent, event_emitter=self.event_emitter)
        await self._emit_exit(next_node.node_name, "Query analysis complete, proceeding to filter building")
        return next_node


@dataclass
class FilterBuildingNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    async def run(self, ctx: GraphRunContext[SearchState, None]) -> ExecutionNode:
        """Route to next node after filter building.

        The agent execution happened during stream(), so ctx.state is already updated.
        This method just handles routing logic.

        Returns:
            ExecutionNode - always route to execution
        """
        logger.debug(
            f"{self.node_name}: Filter building complete",
            has_filters=ctx.state.query.filters is not None if ctx.state.query else False,
        )

        next_node = ExecutionNode(search_agent=self.search_agent, event_emitter=self.event_emitter)
        await self._emit_exit(next_node.node_name, "Filter building complete, proceeding to execution")
        return next_node


@dataclass
class ExecutionNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    async def run(self, ctx: GraphRunContext[SearchState, None]) -> ResultProcessingNode | ResponseNode:
        """Route to next node after execution."""
        logger.debug(
            f"{self.node_name}: Execution complete",
            results_count=ctx.state.results_count,
        )

        # Always go to ResponseNode (ResultProcessingNode is kept for future use)
        # Future: Could route to ResultProcessingNode for export/details functionality
        next_node: ResultProcessingNode | ResponseNode = ResponseNode(
            search_agent=self.search_agent, event_emitter=self.event_emitter
        )
        await self._emit_exit(next_node.node_name, "Execution complete, proceeding to response")
        return next_node


@dataclass
class ResultProcessingNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    async def run(self, ctx: GraphRunContext[SearchState, None]) -> ResponseNode:
        """Route to next node after result processing.

        The agent execution happened during stream(), so ctx.state is already updated.
        This method just handles routing logic.

        Returns:
            ResponseNode - always route to response
        """
        logger.debug(f"{self.node_name}: Result processing complete")

        next_node = ResponseNode(search_agent=self.search_agent, event_emitter=self.event_emitter)
        await self._emit_exit(next_node.node_name, "Results processed, proceeding to response")
        return next_node


@dataclass
class ResponseNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    async def run(self, ctx: GraphRunContext[SearchState, None]) -> End[str]:
        """Return final output after response generation.

        The agent execution happened during stream(), which generated the response text.
        This method just emits final events and returns End.

        Returns:
            End with response text
        """
        # For now, return a simple completion message
        # TODO: Get actual response output from streaming agent execution
        output = f"Search completed. Found {ctx.state.results_count or 0} results."

        logger.info(f"{self.node_name}: Response generation complete", response_output=output)

        # Emit EXIT event (no next node since this is the end)
        await self._emit_exit(None, "Response generation complete")

        return End(output)

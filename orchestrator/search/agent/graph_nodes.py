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
    get_aggregation_execution_prompt,
    get_filter_building_prompt,
    get_intent_prompt,
    get_query_init_prompt,
    get_search_execution_prompt,
    get_text_response_prompt,
)
from orchestrator.search.agent.state import IntentType, SearchState
from orchestrator.search.agent.tools import (
    SearchInitParams,
    execution_toolset,
    filter_building_toolset,
    search_toolset,
)
from orchestrator.search.core.types import ActionType
from orchestrator.search.query.queries import AggregateQuery, CountQuery, SelectQuery

logger = structlog.get_logger(__name__)


def _current_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    from time import time_ns

    return time_ns() // 1_000_000


def create_node_agents(model: str) -> dict[str, Agent[StateDeps[SearchState], Any]]:
    """Create specialized agents for each node that needs LLM calls.

    Args:
        model: The LLM model identifier to use for all agents

    Returns:
        Dictionary mapping node names to their specialized Agent instances
    """
    return {
        "intent_agent": Agent(
            model=model,
            deps_type=StateDeps[SearchState],
            output_type=IntentType,
            retries=2,
            system_prompt=get_intent_prompt(),
        ),
        "query_init_agent": Agent(
            model=model,
            deps_type=StateDeps[SearchState],
            output_type=SearchInitParams,
            retries=2,
            system_prompt=get_query_init_prompt(),
        ),
        "filter_building_agent": Agent(
            model=model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[filter_building_toolset],
        ),
        "search_agent": Agent(
            model=model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[execution_toolset],
        ),
        "aggregation_agent": Agent(
            model=model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[filter_building_toolset, execution_toolset],
        ),
        "text_response_agent": Agent(
            model=model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[search_toolset],
        ),
    }


# Node descriptions for graph visualization
NODE_DESCRIPTIONS = {
    "IntentNode": "Classifies user intent and initializes query",
    "FilterBuildingNode": "Builds database query filters using FilterTree",
    "SearchNode": "Executes database searches",
    "AggregationNode": "Executes aggregations with grouping and visualization",
    "TextResponseNode": "Generates text responses for general questions",
}


@dataclass
class BaseGraphNode:
    """Base class for all graph nodes with common fields and streaming logic."""

    node_agent: Agent[StateDeps["SearchState"], Any]  # Dedicated agent for this node
    event_emitter: Callable[[BaseEvent], Awaitable[None]] | None = None

    @property
    def node_name(self) -> str:
        """Get the name of this node for event emission."""
        return self.__class__.__name__

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the prompt for this node's agent. Override in subclasses that need dynamic prompts."""
        raise NotImplementedError(f"{self.node_name} must implement get_prompt() or override stream()")

    async def event_generator(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AgentStreamEvent]:
        """Generate events from the node's dedicated agent as they happen."""
        # Emit GRAPH_NODE_ENTER event at the start
        if hasattr(self, "event_emitter") and self.event_emitter:
            value: GraphNodeEnterValue = {"node": self.node_name, "step_type": "graph_node"}
            graph_event = GraphNodeEnterEvent(timestamp=_current_timestamp_ms(), value=value)
            await self.event_emitter(graph_event)

        prompt = self.get_prompt(ctx)
        state_deps = StateDeps(ctx.state)

        # Use the node's dedicated agent
        async with self.node_agent.iter(
            user_prompt=prompt,
            deps=state_deps,
            message_history=[],
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
class IntentNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    user_input: str = field(kw_only=True)
    intent_agent: Agent[StateDeps[SearchState], IntentType] = field(kw_only=True)  # Separate intent classifier
    query_init_agent: Agent[StateDeps[SearchState], Any] = field(kw_only=True)  # For calling start_new_search
    agents: dict[str, Agent[StateDeps[SearchState], Any]] = field(kw_only=True)  # All agents for routing

    @asynccontextmanager
    async def stream(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AsyncIterator[AgentStreamEvent]]:
        """Use intent_agent to classify user input, then call start_new_search."""

        async def event_generator() -> AsyncIterator[AgentStreamEvent]:
            # Emit enter event
            if self.event_emitter:
                value: GraphNodeEnterValue = {"node": self.node_name, "step_type": "graph_node"}
                await self.event_emitter(GraphNodeEnterEvent(timestamp=_current_timestamp_ms(), value=value))

            state_deps = StateDeps(ctx.state)

            # Run intent classification (no streaming, just get result)
            result = await self.intent_agent.run(self.user_input, deps=state_deps)
            ctx.state.intent = result.output
            logger.debug(f"{self.node_name}: Intent classified", intent=result.output.value)

            # Use query_init_agent to get structured output (entity_type and action)
            prompt = f'Determine entity_type and action for: "{self.user_input}"'

            init_result = await self.query_init_agent.run(
                user_prompt=prompt,
                deps=state_deps,
                message_history=[],
            )

            # Update state
            entity_type = init_result.output.entity_type
            action = init_result.output.action

            # Clear state and initialize query
            ctx.state.results_count = None
            ctx.state.action = action

            # Create the appropriate query object based on action
            if action == ActionType.SELECT:
                ctx.state.query = SelectQuery(entity_type=entity_type, query_text=self.user_input)
            elif action == ActionType.COUNT:
                ctx.state.query = CountQuery(entity_type=entity_type)
            else:  # ActionType.AGGREGATE
                ctx.state.query = AggregateQuery(entity_type=entity_type, aggregations=[])

            logger.debug(
                f"{self.node_name}: Query initialized",
                entity_type=entity_type.value,
                action=action.value,
                query_type=type(ctx.state.query).__name__,
            )

            # Emit exit event
            if self.event_emitter:
                exit_value: GraphNodeExitValue = {
                    "node": self.node_name,
                    "next_node": "routing...",
                    "decision": f"Intent: {ctx.state.intent.value if ctx.state.intent else 'unknown'}",
                }
                await self.event_emitter(GraphNodeExitEvent(timestamp=_current_timestamp_ms(), value=exit_value))

            # Make this a proper async generator
            return
            yield  # pragma: no cover

        yield event_generator()

    async def run(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> FilterBuildingNode | SearchNode | AggregationNode | TextResponseNode:
        """Route based on the intent classified by the agent.

        Returns:
            Appropriate next node based on intent
        """
        intent = ctx.state.intent

        logger.debug(f"{self.node_name}: Routing on intent", intent=intent.value if intent else None)

        # Direct routes without filters
        if intent == IntentType.SEARCH:
            next_node = SearchNode(
                node_agent=self.agents["search_agent"],
                event_emitter=self.event_emitter,
                agents=self.agents,
            )
            await self._emit_exit(next_node.node_name, "Search without filters")
            return next_node

        if intent == IntentType.AGGREGATION:
            next_node = AggregationNode(
                node_agent=self.agents["aggregation_agent"],
                event_emitter=self.event_emitter,
                agents=self.agents,
            )
            await self._emit_exit(next_node.node_name, "Aggregation without filters")
            return next_node

        # Routes through filter building
        if intent == IntentType.SEARCH_WITH_FILTERS or intent == IntentType.AGGREGATION_WITH_FILTERS:
            next_node = FilterBuildingNode(
                node_agent=self.agents["filter_building_agent"],
                event_emitter=self.event_emitter,
                agents=self.agents,
            )
            await self._emit_exit(next_node.node_name, "Search with filters - needs filter building")
            return next_node

        # Fallback for TEXT_RESPONSE or unknown intents
        next_node = TextResponseNode(
            node_agent=self.agents["text_response_agent"],
            event_emitter=self.event_emitter,
        )
        await self._emit_exit(next_node.node_name, f"Text response (intent: {intent.value if intent else 'unknown'})")
        return next_node


@dataclass
class FilterBuildingNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    agents: dict[str, Agent[StateDeps[SearchState], Any]] = field(kw_only=True)  # All agents for routing

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the filter building prompt."""
        return get_filter_building_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> SearchNode | AggregationNode:
        """Route to SearchNode or AggregationNode based on intent.

        Filter building complete - now route to the appropriate execution node.

        Returns:
            SearchNode for SEARCH_WITH_FILTERS, AggregationNode for AGGREGATION_WITH_FILTERS
        """
        intent = ctx.state.intent

        logger.debug(
            f"{self.node_name}: Filter building complete",
            intent=intent.value if intent else None,
            has_filters=ctx.state.query.filters is not None if ctx.state.query else False,
        )

        if intent == IntentType.SEARCH_WITH_FILTERS:
            next_node = SearchNode(
                node_agent=self.agents["search_agent"],
                event_emitter=self.event_emitter,
                agents=self.agents,
            )
            await self._emit_exit(next_node.node_name, "Routing to search execution")
            return next_node

        # AGGREGATION_WITH_FILTERS intent
        next_node = AggregationNode(
            node_agent=self.agents["aggregation_agent"],
            event_emitter=self.event_emitter,
            agents=self.agents,
        )
        await self._emit_exit(next_node.node_name, "Routing to aggregation execution")
        return next_node


@dataclass
class SearchNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    agents: dict[str, Agent[StateDeps[SearchState], Any]] = field(kw_only=True)  # For potential routing

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the search execution prompt."""
        return get_search_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> TextResponseNode:
        """Execute search and route to TextResponseNode for final response.

        Agent has already called run_search() during stream().
        Now route to TextResponseNode to generate user-friendly response.
        """
        logger.info(
            f"{self.node_name}: Search execution complete",
            results_count=ctx.state.results_count,
        )

        next_node = TextResponseNode(
            node_agent=self.agents["text_response_agent"],
            event_emitter=self.event_emitter,
        )
        await self._emit_exit(next_node.node_name, "Search complete, generating response")
        return next_node


@dataclass
class AggregationNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    agents: dict[str, Agent[StateDeps[SearchState], Any]] = field(kw_only=True)  # For potential routing

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the aggregation execution prompt."""
        return get_aggregation_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> TextResponseNode:
        """Execute aggregation and route to TextResponseNode for final response.

        Agent has already called run_aggregation() during stream().
        Now route to TextResponseNode to generate user-friendly response.
        """
        logger.info(
            f"{self.node_name}: Aggregation execution complete",
            results_count=ctx.state.results_count,
        )

        next_node = TextResponseNode(
            node_agent=self.agents["text_response_agent"],
            event_emitter=self.event_emitter,
        )
        await self._emit_exit(next_node.node_name, "Aggregation complete, generating response")
        return next_node


@dataclass
class TextResponseNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the text response prompt."""
        return get_text_response_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> End[str]:
        """Generate text-only response.

        Agent generates appropriate response during stream().
        Just emit exit event and end.
        """
        logger.info(f"{self.node_name}: Text response generation complete")

        output = "Response generated."
        await self._emit_exit(None, "Text response complete")
        return End(output)

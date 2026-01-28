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
    GraphNodeActiveEvent,
    GraphNodeActiveValue,
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

    model: str = field(kw_only=True)  # LLM model identifier
    event_emitter: Callable[[BaseEvent], None] | None = None

    @property
    def node_name(self) -> str:
        """Get the name of this node for event emission."""
        return self.__class__.__name__

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        """Get the agent for this node. Implemented by subclasses."""
        raise NotImplementedError(f"{self.node_name} must implement node_agent property")

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the prompt for this node's agent. Override in subclasses that need dynamic prompts."""
        raise NotImplementedError(f"{self.node_name} must implement get_prompt() or override stream()")

    async def event_generator(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AgentStreamEvent]:
        """Generate events from the node's dedicated agent as they happen."""
        # Emit GRAPH_NODE_ACTIVE event when node becomes active
        if hasattr(self, "event_emitter") and self.event_emitter:
            value: GraphNodeActiveValue = {"node": self.node_name, "step_type": "graph_node"}
            graph_event = GraphNodeActiveEvent(timestamp=_current_timestamp_ms(), value=value)
            self.event_emitter(graph_event)

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

    @asynccontextmanager
    async def stream(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AsyncIterator[AgentStreamEvent]]:
        yield self.event_generator(ctx)


@dataclass
class IntentNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    user_input: str = field(kw_only=True)

    def __post_init__(self):
        """Create the agents needed for this node."""
        self._intent_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            output_type=IntentType,
            retries=2,
            system_prompt=get_intent_prompt(),
        )
        self._query_init_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            output_type=SearchInitParams,
            retries=2,
            system_prompt=get_query_init_prompt(),
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        """IntentNode doesn't use the standard node_agent pattern."""
        raise NotImplementedError("IntentNode uses intent_agent and query_init_agent instead")

    @property
    def intent_agent(self) -> Agent[StateDeps[SearchState], IntentType]:
        return self._intent_agent

    @property
    def query_init_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._query_init_agent

    @asynccontextmanager
    async def stream(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AsyncIterator[AgentStreamEvent]]:
        """Use intent_agent to classify user input, then call start_new_search."""

        async def event_generator() -> AsyncIterator[AgentStreamEvent]:
            # Emit GRAPH_NODE_ACTIVE event
            if self.event_emitter:
                value: GraphNodeActiveValue = {"node": self.node_name, "step_type": "graph_node"}
                self.event_emitter(GraphNodeActiveEvent(timestamp=_current_timestamp_ms(), value=value))

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
            return SearchNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.AGGREGATION:
            return AggregationNode(model=self.model, event_emitter=self.event_emitter)

        # Routes through filter building
        if intent == IntentType.SEARCH_WITH_FILTERS or intent == IntentType.AGGREGATION_WITH_FILTERS:
            return FilterBuildingNode(model=self.model, event_emitter=self.event_emitter)

        # Fallback for TEXT_RESPONSE or unknown intents
        return TextResponseNode(model=self.model, event_emitter=self.event_emitter)


@dataclass
class FilterBuildingNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    def __post_init__(self):
        """Create the agent for this node."""
        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[filter_building_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

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
            return SearchNode(model=self.model, event_emitter=self.event_emitter)

        # AGGREGATION_WITH_FILTERS intent
        return AggregationNode(model=self.model, event_emitter=self.event_emitter)


@dataclass
class SearchNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    def __post_init__(self):
        """Create the agent for this node."""
        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[execution_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the search execution prompt."""
        return get_search_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> TextResponseNode:
        return TextResponseNode(model=self.model, event_emitter=self.event_emitter)


@dataclass
class AggregationNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    def __post_init__(self):
        """Create the agent for this node."""
        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[filter_building_toolset, execution_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the aggregation execution prompt."""
        return get_aggregation_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> TextResponseNode:
        return TextResponseNode(model=self.model, event_emitter=self.event_emitter)


@dataclass
class TextResponseNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    def __post_init__(self):
        """Create the agent for this node."""
        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[search_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the text response prompt."""
        return get_text_response_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> End[str]:
        return End("Response generated.")


def emit_end_event(event_emitter: Callable[[BaseEvent], None] | None) -> None:
    """Emit GRAPH_NODE_ACTIVE event for End node."""
    if event_emitter:
        event_emitter(
            GraphNodeActiveEvent(
                timestamp=_current_timestamp_ms(), value={"node": End.__name__, "step_type": "graph_node"}
            )
        )

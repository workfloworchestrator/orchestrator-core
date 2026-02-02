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
from textwrap import dedent
from typing import Any, AsyncIterator, Callable

import structlog
from ag_ui.core import BaseEvent
from pydantic_ai import Agent
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import AgentStreamEvent
from pydantic_ai.run import AgentRunResultEvent
from pydantic_graph import BaseNode, End, GraphRunContext

from orchestrator.search.agent.graph_events import (
    GraphNodeActiveEvent,
    GraphNodeActiveValue,
)
from orchestrator.search.agent.prompts import (
    get_aggregation_execution_prompt,
    get_search_execution_prompt,
    get_text_response_prompt,
)
from orchestrator.search.agent.state import IntentType, SearchState
from orchestrator.search.agent.tools import (
    aggregation_toolset,
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

    async def event_generator(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> AsyncIterator[AgentStreamEvent | AgentRunResultEvent[Any]]:
        """Generate events from the node's dedicated agent as they happen."""
        # Emit GRAPH_NODE_ACTIVE event when node becomes active
        if hasattr(self, "event_emitter") and self.event_emitter:
            value: GraphNodeActiveValue = {"node": self.node_name, "step_type": "graph_node"}
            graph_event = GraphNodeActiveEvent(timestamp=_current_timestamp_ms(), value=value)
            self.event_emitter(graph_event)

        prompt = self.get_prompt(ctx)
        state_deps = StateDeps(ctx.state)

        # Use the node's dedicated agent with AG-UI event processing
        async for event in self.node_agent.run_stream_events(
            user_prompt=prompt,
            deps=state_deps,
            message_history=[],
        ):
            yield event

    @asynccontextmanager
    async def stream(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> AsyncIterator[AsyncIterator[AgentStreamEvent | AgentRunResultEvent[Any]]]:
        yield self.event_generator(ctx)


@dataclass
class IntentNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Classifies user intent and initializes query", init=False)
    user_input: str = field(kw_only=True)

    def __post_init__(self):
        """Create the agent for this node."""
        from orchestrator.search.agent.tools import IntentAndQueryInit

        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            output_type=IntentAndQueryInit,
            retries=2,
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        """Get the combined intent and query init agent."""
        return self._node_agent

    @asynccontextmanager
    async def stream(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AsyncIterator[AgentStreamEvent]]:
        """Classify intent and initialize query in single LLM call."""

        async def event_generator() -> AsyncIterator[AgentStreamEvent]:
            # Emit GRAPH_NODE_ACTIVE event
            if self.event_emitter:
                value: GraphNodeActiveValue = {"node": self.node_name, "step_type": "graph_node"}
                self.event_emitter(GraphNodeActiveEvent(timestamp=_current_timestamp_ms(), value=value))

            state_deps = StateDeps(ctx.state)

            # Check what has been completed from state
            from orchestrator.search.core.types import ActionType

            query_executed = ctx.state.action is not None  # Check if SELECT/COUNT/AGGREGATE was executed
            export_done = ctx.state.export_url is not None

            if export_done:
                # Export completed, all work is done
                ctx.state.intent = IntentType.TEXT_RESPONSE
                logger.debug(f"{self.node_name}: Export complete, ending flow")
                # Skip LLM call
                return
                yield  # pragma: no cover

            if query_executed:
                # After search/aggregation, check if user requested additional actions
                query_json = ctx.state.query.model_dump_json(indent=2, exclude_none=True) if ctx.state.query else "{}"

                prompt = dedent(
                    f"""
                    Executed query:
                    {query_json}

                    Original user request: {self.user_input}

                    Determine if user requested ADDITIONAL actions beyond what was executed:
                    - If user explicitly requested to export or fetch details: classify as 'result_actions'
                    - If the executed query satisfies the entire request: classify as 'text_response'

                    Examples:
                    - Request: "search for subscriptions", Executed: SELECT query → text_response (done)
                    - Request: "search for subscriptions AND export them", Executed: SELECT query → result_actions (export next)
                    - Request: "count subscriptions per month", Executed: COUNT with temporal grouping → text_response (done)
                    - Request: "what is the average price", Executed: AGGREGATE query → text_response (done)
                    """
                ).strip()
            else:
                # First routing, classify initial intent
                prompt = f"User request: {self.user_input}"

            # Single LLM call for intent classification and query initialization
            result = await self.node_agent.run(prompt, deps=state_deps)

            # Extract intent
            ctx.state.intent = result.output.intent

            # Only initialize query for search/aggregation intents (not result_actions or text_response)
            if result and result.output.intent in (IntentType.SEARCH, IntentType.AGGREGATION):
                entity_type = result.output.entity_type
                action = result.output.action

                if not entity_type or not action:
                    raise ValueError("entity_type and action required for search/aggregation intents")

                logger.debug(
                    f"{self.node_name}: Intent classified and query initialized",
                    intent=result.output.intent.value,
                    entity_type=entity_type.value,
                    action=action.value,
                )

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
            else:
                intent_value = None
                if result:
                    intent_value = result.output.intent.value
                elif ctx.state.intent:
                    intent_value = ctx.state.intent.value
                logger.debug(f"{self.node_name}: Intent classified", intent=intent_value)

            # Make this a proper async generator
            return
            yield  # pragma: no cover

        yield event_generator()

    async def run(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> SearchNode | AggregationNode | ResultActionsNode | TextResponseNode | End[str]:
        """Route based on the intent classified by the agent.

        Returns:
            Appropriate action node based on intent, or End to pause
        """
        intent = ctx.state.intent

        logger.debug(f"{self.node_name}: Routing on intent", intent=intent.value if intent else None)

        if intent == IntentType.SEARCH:
            return SearchNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.AGGREGATION:
            return AggregationNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.RESULT_ACTIONS:
            return ResultActionsNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.TEXT_RESPONSE:
            # All work complete, pause the graph
            return End("Complete")

        # Unknown state, end
        return End("No action needed")


@dataclass
class SearchNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Executes database searches with optional filtering", init=False)

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
        """Get the search execution prompt."""
        return get_search_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> IntentNode | End[str]:
        """After search completes, emit state and route back to IntentNode."""
        # Emit STATE_SNAPSHOT for state persistence (after run_search modified state)
        if self.event_emitter:
            from ag_ui.core import EventType, StateSnapshotEvent
            state_event = StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                timestamp=_current_timestamp_ms(),
                snapshot=ctx.state.model_dump()
            )
            self.event_emitter(state_event)

        return IntentNode(model=self.model, event_emitter=self.event_emitter, user_input=ctx.state.user_input)


@dataclass
class AggregationNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Executes aggregations with grouping, filtering, and visualization", init=False)

    def __post_init__(self):
        """Create the agent for this node."""
        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[filter_building_toolset, aggregation_toolset, execution_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the aggregation execution prompt."""
        return get_aggregation_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> IntentNode | End[str]:
        """After aggregation completes, emit state and route back to IntentNode."""
        # Emit STATE_SNAPSHOT for state persistence (after run_aggregation modified state)
        if self.event_emitter:
            from ag_ui.core import EventType, StateSnapshotEvent
            state_event = StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                timestamp=_current_timestamp_ms(),
                snapshot=ctx.state.model_dump()
            )
            self.event_emitter(state_event)

        return IntentNode(model=self.model, event_emitter=self.event_emitter, user_input=ctx.state.user_input)


@dataclass
class ResultActionsNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Exports, fetches details, or visualizes existing results", init=False)

    def __post_init__(self):
        """Create the agent for this node."""
        from orchestrator.search.agent.tools import result_actions_toolset

        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            retries=2,
            toolsets=[result_actions_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the result actions prompt."""
        results_count = ctx.state.results_count or 0
        return dedent(
            f"""
            Act on existing search/aggregation results.

            Current state: {results_count} results available from previous query.

            Available actions:
            - Export results: Call prepare_export()
            - Fetch entity details: Call fetch_entity_details(limit=...)

            User request: {ctx.state.user_input}

            Execute the requested action and provide a brief confirmation.
            """
        ).strip()

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> IntentNode | End[str]:
        """After result action completes, emit state and route back to IntentNode."""
        # Emit STATE_SNAPSHOT for state persistence (after prepare_export modified state)
        if self.event_emitter:
            from ag_ui.core import EventType, StateSnapshotEvent
            state_event = StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                timestamp=_current_timestamp_ms(),
                snapshot=ctx.state.model_dump()
            )
            self.event_emitter(state_event)

        return IntentNode(model=self.model, event_emitter=self.event_emitter, user_input=ctx.state.user_input)


@dataclass
class TextResponseNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Generates text responses for general questions", init=False)

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
        """Text response completes the flow."""
        return End("Complete")


def emit_end_event(event_emitter: Callable[[BaseEvent], None] | None) -> None:
    """Emit GRAPH_NODE_ACTIVE event for End node."""
    if event_emitter:
        event_emitter(
            GraphNodeActiveEvent(
                timestamp=_current_timestamp_ms(), value={"node": End.__name__, "step_type": "graph_node"}
            )
        )

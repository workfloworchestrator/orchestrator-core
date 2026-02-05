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
from typing import Any, AsyncIterator, Callable

import structlog
from ag_ui.core import BaseEvent
from pydantic_ai import Agent
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
)
from pydantic_ai.run import AgentRunResultEvent
from pydantic_graph import BaseNode, End, GraphRunContext

from orchestrator.search.agent.graph_events import (
    GraphNodeActiveEvent,
    GraphNodeActiveValue,
)
from orchestrator.search.agent.prompts import (
    get_aggregation_execution_prompt,
    get_intent_classification_prompt,
    get_result_actions_prompt,
    get_search_execution_prompt,
    get_text_response_prompt,
)
from orchestrator.search.agent.state import IntentType, SearchState
from orchestrator.search.agent.tools import (
    aggregation_toolset,
    execution_toolset,
    filter_building_toolset,
)
from orchestrator.search.core.types import QueryOperation
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
    _tool_calls_in_current_run: list[str] = field(default_factory=list, init=False, repr=False)
    _last_run_result: Any | None = field(default=None, init=False, repr=False)

    @property
    def node_name(self) -> str:
        """Get the name of this node for event emission."""
        return self.__class__.__name__

    def emit_node_active_event(self) -> None:
        """Emit GRAPH_NODE_ACTIVE event for this node."""
        if self.event_emitter:
            value: GraphNodeActiveValue = {"node": self.node_name, "step_type": "graph_node"}
            self.event_emitter(GraphNodeActiveEvent(timestamp=_current_timestamp_ms(), value=value))

    def record_node_visit(self, ctx: GraphRunContext[SearchState, None], action_description: str) -> None:
        """Record this node's visit with an iteration number to track multiple visits.

        Args:
            ctx: Graph run context containing state
            action_description: Description of what this node did
        """
        iteration = len([k for k in ctx.state.visited_nodes.keys() if k.startswith(self.__class__.__name__)]) + 1
        key = f"{self.__class__.__name__}_{iteration}"
        ctx.state.visited_nodes[key] = action_description

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
        self.emit_node_active_event()

        # Reset tool calls tracking and result for this run
        self._tool_calls_in_current_run = []
        self._last_run_result = None

        prompt = self.get_prompt(ctx)
        state_deps = StateDeps(ctx.state)

        # Use the node's dedicated agent with AG-UI event processing
        async for event in self.node_agent.run_stream_events(
            instructions=prompt,
            deps=state_deps,
            message_history=ctx.state.message_history,
        ):
            # Track tool calls as they happen
            try:
                if isinstance(event, FunctionToolCallEvent):
                    self._tool_calls_in_current_run.append(event.part.tool_name)
            except Exception as e:
                logger.error(f"Error tracking tool call: {e}", exc_info=True)

            # Capture the final result event
            if isinstance(event, AgentRunResultEvent):
                self._last_run_result = event.result
                logger.debug(
                    f"{self.node_name}: Captured final result with {len(event.result.new_messages())} new messages"
                )

            yield event

        # After streaming completes, append new messages to state
        if self._last_run_result is not None:
            new_messages = self._last_run_result.new_messages()
            ctx.state.message_history.extend(new_messages)
            logger.debug(
                f"{self.node_name}: Appended {len(new_messages)} new messages to history",
                total_messages=len(ctx.state.message_history),
            )
        else:
            logger.warning(f"{self.node_name}: No result captured - messages NOT updated")

    @asynccontextmanager
    async def stream(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> AsyncIterator[AsyncIterator[AgentStreamEvent | AgentRunResultEvent[Any]]]:
        yield self.event_generator(ctx)


@dataclass
class IntentNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Classifies user intent and initializes query", init=False)

    def __post_init__(self):
        """Create the agent for this node."""
        from orchestrator.search.agent.tools import IntentAndQueryInit

        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            output_type=IntentAndQueryInit,
            name="classify_intent",
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
            self.emit_node_active_event()
            prompt = get_intent_classification_prompt(
                user_input=ctx.state.user_input,
                visited_nodes=ctx.state.visited_nodes,
            )
            logger.debug(prompt=prompt)

            # Single LLM call for intent classification and query initialization
            result = await self.node_agent.run(
                instructions=prompt, message_history=ctx.state.message_history, deps=StateDeps(ctx.state)
            )

            # Append new messages to state so subsequent nodes can see this conversation
            new_messages = result.new_messages()
            ctx.state.message_history.extend(new_messages)
            logger.debug(
                f"{self.node_name}: Appended {len(new_messages)} new messages to history",
                total_messages=len(ctx.state.message_history),
            )

            # Extract intent
            logger.debug(
                f"{self.node_name}: LLM response received",
                intent=result.output.intent.value if result and result.output else None,
                entity_type=(
                    result.output.entity_type.value if result and result.output and result.output.entity_type else None
                ),
                query_operation=result.output.query_operation.value if result and result.output and result.output.query_operation else None,
            )

            ctx.state.intent = result.output.intent
            ctx.state.end_actions = result.output.end_actions

            # Only initialize query for search/aggregation intents (not result_actions or text_response)
            if result and result.output.intent in (IntentType.SEARCH, IntentType.AGGREGATION):
                entity_type = result.output.entity_type
                query_operation = result.output.query_operation

                if not entity_type or not query_operation:
                    raise ValueError("entity_type and query_operation required for search/aggregation intents")

                logger.debug(
                    f"{self.node_name}: Intent classified and query initialized",
                    intent=result.output.intent.value,
                    entity_type=entity_type.value,
                    query_operation=query_operation.value,
                )

                # Clear state and initialize query
                ctx.state.results_count = None
                ctx.state.query_operation = query_operation

                # Create the appropriate query object based on query_operation
                if query_operation == QueryOperation.SELECT:
                    ctx.state.query = SelectQuery(entity_type=entity_type, query_text=ctx.state.user_input)
                elif query_operation == QueryOperation.COUNT:
                    ctx.state.query = CountQuery(entity_type=entity_type)
                else:  # QueryOperation.AGGREGATE
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
            Appropriate action node based on intent, TextResponseNode for completion message, or End if work is done
        """
        intent = ctx.state.intent

        logger.debug(f"{self.node_name}: Routing on intent", intent=intent.value if intent else None)

        # Record the routing decision
        if intent:
            self.record_node_visit(ctx, f"Routed to {intent.value}")

        if intent == IntentType.SEARCH:
            return SearchNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.AGGREGATION:
            return AggregationNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.RESULT_ACTIONS:
            return ResultActionsNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.TEXT_RESPONSE:
            return TextResponseNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.NO_MORE_ACTIONS:
            # Only route to TextResponseNode if no actions were performed (to avoid silent end)
            # If actions were performed, they already streamed results to user, so just end
            if not ctx.state.visited_nodes:
                return TextResponseNode(model=self.model, event_emitter=self.event_emitter)
            return End("Complete")

        # If we have actions, end; otherwise send completion message
        if ctx.state.visited_nodes:
            return End("Complete")
        return TextResponseNode(model=self.model, event_emitter=self.event_emitter)


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
        """After search completes, route back to IntentNode or End based on end_actions flag."""
        query = ctx.state.query
        if query:
            query_json = query.model_dump_json(indent=2)
            results = ctx.state.results_count or 0
            self.record_node_visit(ctx, f"Executed search, {results} results:\n{query_json}")

        if ctx.state.end_actions:
            return End("Complete")

        return IntentNode(model=self.model, event_emitter=self.event_emitter)


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
        """After aggregation completes, route back to IntentNode or End based on end_actions flag."""
        query = ctx.state.query
        if query:
            query_json = query.model_dump_json(indent=2)
            results = ctx.state.results_count or 0
            self.record_node_visit(ctx, f"Executed aggregation, {results} groups:\n{query_json}")

        if ctx.state.end_actions:
            return End("Complete")

        return IntentNode(model=self.model, event_emitter=self.event_emitter)


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
        return get_result_actions_prompt(results_count)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> IntentNode | End[str]:
        """After result action completes, route back to IntentNode or End based on end_actions flag."""
        # Record what this node did based on which tool was called
        if "prepare_export" in self._tool_calls_in_current_run:
            self.record_node_visit(ctx, "Export has been executed and download link delivered to user")
        elif "fetch_entity_details" in self._tool_calls_in_current_run:
            self.record_node_visit(ctx, "Entity details have been fetched and delivered to user")
        else:
            # Fallback if no tool was called (shouldn't happen)
            self.record_node_visit(ctx, "Result action completed")

        if ctx.state.end_actions:
            return End("Complete")

        return IntentNode(model=self.model, event_emitter=self.event_emitter)


@dataclass
class TextResponseNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    """Generates text responses for general questions or completion acknowledgments.

    This node handles two cases:
    1. TEXT_RESPONSE intent: User asks general questions, greetings, or out-of-scope queries
    2. NO_MORE_ACTIONS intent: Generates a brief completion message when work is done
    """

    description: str = field(default="Generates text responses for general questions", init=False)

    def __post_init__(self):
        """Create the agent for this node."""
        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the text response prompt (delegates to prompts.py)."""
        # Only forced response if NO_MORE_ACTIONS and no actions were performed
        is_forced = ctx.state.intent == IntentType.NO_MORE_ACTIONS and not ctx.state.visited_nodes
        return get_text_response_prompt(ctx.state, is_forced_response=is_forced)

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

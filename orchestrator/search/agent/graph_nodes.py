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
from time import time_ns
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

from orchestrator.search.agent import tools
from orchestrator.search.agent.environment import NodeStep, ToolStep
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
    IntentAndQueryInit,
    aggregation_execution_toolset,
    aggregation_toolset,
    filter_building_toolset,
    result_actions_toolset,
    search_execution_toolset,
)
from orchestrator.search.core.types import QueryOperation
from orchestrator.search.query.queries import AggregateQuery, CountQuery, SelectQuery

logger = structlog.get_logger(__name__)


def _current_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
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

    def record_node_entry(self, ctx: GraphRunContext[SearchState, None]) -> None:
        """Record entering this node as a NodeStep."""
        # Finish previous node if any
        if ctx.state.environment.current_turn and ctx.state.environment.current_turn.current_node_step:
            ctx.state.environment.finish_node_step()

        # Start new node step
        node_step = NodeStep(
            step_type=self.__class__.__name__,
            description=f"Executing {self.__class__.__name__}",
        )
        ctx.state.environment.start_node_step(node_step)

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
        # Pass empty message_history, nodes use prompts with our managed environment context
        async for event in self.node_agent.run_stream_events(
            instructions=prompt,
            deps=state_deps,
            message_history=[],
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

        if self._last_run_result is None:
            logger.warning(f"{self.node_name}: No result captured")

    @asynccontextmanager
    async def stream(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> AsyncIterator[AsyncIterator[AgentStreamEvent | AgentRunResultEvent[Any]]]:
        yield self.event_generator(ctx)


@dataclass
class IntentNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Classifies user intent and initializes query", init=False)
    _decision_reason: str | None = field(default=None, init=False)

    def __post_init__(self):
        """Create the agent for this node."""
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
            self.emit_node_active_event()
            prompt = get_intent_classification_prompt(ctx.state)
            print(prompt)
            result = await self.node_agent.run(instructions=prompt, message_history=[], deps=StateDeps(ctx.state))

            # Extract intent
            logger.debug(
                f"{self.node_name}: LLM response received",
                intent=result.output.intent.value if result and result.output else None,
                entity_type=(
                    result.output.entity_type.value if result and result.output and result.output.entity_type else None
                ),
                query_operation=(
                    result.output.query_operation.value
                    if result and result.output and result.output.query_operation
                    else None
                ),
                end_actions=result.output.end_actions if result and result.output else None,
            )

            ctx.state.intent = result.output.intent
            ctx.state.end_actions = result.output.end_actions

            # Store decision_reason on the node instance so run() can use it after record_node_entry()
            self._decision_reason = result.output.decision_reason

            # Only initialize query for search/aggregation intents (not result_actions or text_response)
            if result and result.output.intent in (IntentType.SEARCH, IntentType.AGGREGATION):
                entity_type = result.output.entity_type
                query_operation = result.output.query_operation

                if not entity_type or not query_operation:
                    raise ValueError("entity_type and query_operation required for search/aggregation intents")

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
        self.record_node_entry(ctx)

        # Apply decision_reason to the node step we just created
        if (
            self._decision_reason
            and ctx.state.environment.current_turn
            and ctx.state.environment.current_turn.current_node_step
        ):
            ctx.state.environment.current_turn.current_node_step.decision_reason = self._decision_reason

        intent = ctx.state.intent

        if intent == IntentType.SEARCH:
            return SearchNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.AGGREGATION:
            return AggregationNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.RESULT_ACTIONS:
            return ResultActionsNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.TEXT_RESPONSE:
            return TextResponseNode(model=self.model, event_emitter=self.event_emitter)

        if intent == IntentType.NO_MORE_ACTIONS:
            # Only route to TextResponseNode if no steps were performed (to avoid silent end)
            # If steps were performed, they already streamed results to user, so just end
            has_steps = ctx.state.environment.current_turn and (
                len(ctx.state.environment.current_turn.node_steps) > 0
                or ctx.state.environment.current_turn.current_node_step is not None
            )
            if not has_steps:
                return TextResponseNode(model=self.model, event_emitter=self.event_emitter)
            ctx.state.environment.complete_turn(
                assistant_answer="Complete",
                query_id=ctx.state.query_id,
            )
            return End("Complete")

        # If we have steps, end; otherwise send completion message
        has_steps = ctx.state.environment.current_turn and (
            len(ctx.state.environment.current_turn.node_steps) > 0
            or ctx.state.environment.current_turn.current_node_step is not None
        )
        if has_steps:
            ctx.state.environment.complete_turn(
                assistant_answer="Complete",
                query_id=ctx.state.query_id,
            )
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
            toolsets=[filter_building_toolset, search_execution_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the search execution prompt."""
        prompt = get_search_execution_prompt(ctx.state)
        print(prompt)
        return prompt

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> IntentNode | End[str]:
        self.record_node_entry(ctx)
        query = ctx.state.query
        if query:
            results = ctx.state.results_count or 0

            ctx.state.environment.record_tool_step(
                ToolStep(
                    step_type="run_search",
                    description=f"Searched {results} {query.entity_type.value}",
                    entity_type=query.entity_type.value,
                    results_count=results,
                    query_operation=ctx.state.query_operation.value if ctx.state.query_operation else None,
                    query_snapshot=query.model_dump(),
                    success=True,
                )
            )

        if ctx.state.end_actions:
            ctx.state.environment.complete_turn(
                assistant_answer="Complete",
                query_id=ctx.state.query_id,
            )
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
            toolsets=[filter_building_toolset, aggregation_toolset, aggregation_execution_toolset],
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        return self._node_agent

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the aggregation execution prompt."""
        prompt = get_aggregation_execution_prompt(ctx.state)
        print(prompt)
        return prompt

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> IntentNode | End[str]:
        self.record_node_entry(ctx)
        query = ctx.state.query
        if query:
            results = ctx.state.results_count or 0

            ctx.state.environment.record_tool_step(
                ToolStep(
                    step_type="run_aggregation",
                    description=f"Aggregated {results} groups for {query.entity_type.value}",
                    entity_type=query.entity_type.value,
                    results_count=results,
                    query_operation=ctx.state.query_operation.value if ctx.state.query_operation else None,
                    query_snapshot=query.model_dump(),
                    success=True,
                )
            )

        if ctx.state.end_actions:
            ctx.state.environment.complete_turn(
                assistant_answer="Complete",
                query_id=ctx.state.query_id,
            )
            return End("Complete")

        return IntentNode(model=self.model, event_emitter=self.event_emitter)


@dataclass
class ResultActionsNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    description: str = field(default="Exports, fetches details, or visualizes existing results", init=False)

    def __post_init__(self):
        """Create the agent for this node."""
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
        prompt = get_result_actions_prompt(ctx.state)
        print(prompt)
        return prompt

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> IntentNode | End[str]:
        self.record_node_entry(ctx)

        tool_action_map = {
            tools.prepare_export.__name__: ("export", "Prepared export for results"),
            tools.fetch_entity_details.__name__: ("fetch_details", "Fetched entity details"),
        }

        logger.debug(
            f"{self.__class__.__name__}: Tool calls tracked",
            tool_calls=self._tool_calls_in_current_run,
        )

        # Record step for the tool that was called
        for tool_name in self._tool_calls_in_current_run:
            if tool_name in tool_action_map:
                step_type, description = tool_action_map[tool_name]

                # Capture query snapshot if available (shows what results are being acted on)
                query_snapshot = None
                if ctx.state.query:
                    query_snapshot = ctx.state.query.model_dump()

                ctx.state.environment.record_tool_step(
                    ToolStep(
                        step_type=step_type,
                        description=description,
                        results_count=ctx.state.results_count or 0,
                        success=True,
                        query_snapshot=query_snapshot,
                    )
                )
                break

        if ctx.state.end_actions:
            ctx.state.environment.complete_turn(
                assistant_answer="Complete",
                query_id=ctx.state.query_id,
            )
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
        # Only forced response if NO_MORE_ACTIONS and no steps were performed
        has_steps = ctx.state.environment.current_turn and (
            len(ctx.state.environment.current_turn.node_steps) > 0
            or ctx.state.environment.current_turn.current_node_step is not None
        )
        is_forced = ctx.state.intent == IntentType.NO_MORE_ACTIONS and not has_steps
        return get_text_response_prompt(ctx.state, is_forced_response=is_forced)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> End[str]:
        """Text response completes the flow."""
        self.record_node_entry(ctx)
        ctx.state.environment.complete_turn(
            assistant_answer="Complete",
            query_id=ctx.state.query_id,
        )
        return End("Complete")


def emit_end_event(event_emitter: Callable[[BaseEvent], None] | None) -> None:
    """Emit GRAPH_NODE_ACTIVE event for End node."""
    if event_emitter:
        event_emitter(
            GraphNodeActiveEvent(
                timestamp=_current_timestamp_ms(), value={"node": End.__name__, "step_type": "graph_node"}
            )
        )

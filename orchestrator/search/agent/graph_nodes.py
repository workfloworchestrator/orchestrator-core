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

from abc import ABC, abstractmethod
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

from orchestrator.search.agent.environment import MemoryScope, ToolStep
from orchestrator.search.agent.graph_events import (
    GraphNodeActiveEvent,
    GraphNodeActiveValue,
)
from orchestrator.search.agent.prompts import (
    get_aggregation_execution_prompt,
    get_planning_prompt,
    get_result_actions_prompt,
    get_search_execution_prompt,
    get_text_response_prompt,
)
from orchestrator.search.agent.state import ExecutionPlan, SearchState, TaskAction, TaskStatus
from orchestrator.search.agent.tools import (
    aggregation_execution_toolset,
    aggregation_toolset,
    filter_building_toolset,
    result_actions_toolset,
    search_execution_toolset,
)
from orchestrator.search.agent.utils import current_timestamp_ms, log_agent_request, log_execution_plan

logger = structlog.get_logger(__name__)


@dataclass
class BaseGraphNode(ABC):
    """Base class for all graph nodes with common fields and streaming logic."""

    model: str = field(kw_only=True)  # LLM model identifier
    event_emitter: Callable[[BaseEvent], None] | None = None
    debug: bool = False  # Enable debug logging
    _tool_calls_in_current_run: list[str] = field(default_factory=list, init=False, repr=False)
    _last_run_result: Any | None = field(default=None, init=False, repr=False)

    @property
    def node_name(self) -> str:
        """Get the name of this node for event emission."""
        return self.__class__.__name__

    def emit_node_active_event(self, ctx: GraphRunContext[SearchState, None] | None = None) -> None:
        """Emit GRAPH_NODE_ACTIVE event for this node."""
        if self.event_emitter:
            value: GraphNodeActiveValue = {"node": self.node_name, "step_type": "graph_node"}

            # Add reasoning if available from current task
            if ctx and ctx.state.execution_plan:
                task = ctx.state.execution_plan.current
                if task and task.reasoning:
                    value["reasoning"] = task.reasoning

            self.event_emitter(GraphNodeActiveEvent(timestamp=current_timestamp_ms(), value=value))

    @property
    @abstractmethod
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        """Get the agent for this node. Must be implemented by subclasses."""
        ...

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the prompt for this node's agent. Must be implemented by nodes using event_generator."""
        raise NotImplementedError(f"{self.node_name} must implement get_prompt() if using default event_generator()")

    def get_message_history(self, ctx: GraphRunContext[SearchState, None]):
        """Get message history for this node. Override in subclasses that need different scope."""
        # Default: LIGHTWEIGHT scope (query summaries without full traces)
        return ctx.state.environment.get_message_history(max_turns=5, scope=MemoryScope.LIGHTWEIGHT)

    async def event_generator(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> AsyncIterator[AgentStreamEvent | AgentRunResultEvent[Any]]:
        """Generate events from the node's dedicated agent as they happen."""
        # Emit GRAPH_NODE_ACTIVE event when node becomes active
        self.emit_node_active_event(ctx)

        # Reset tool calls tracking and result for this run
        self._tool_calls_in_current_run = []
        self._last_run_result = None

        prompt = self.get_prompt(ctx)
        message_history = self.get_message_history(ctx)
        state_deps = StateDeps(ctx.state)

        if self.debug:
            log_agent_request(self.node_name, prompt, message_history)

        # Use the node's dedicated agent with AG-UI event processing
        async for event in self.node_agent.run_stream_events(
            instructions=prompt,
            deps=state_deps,
            message_history=message_history,
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
class PlannerNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    """Plans and orchestrates multi-step task execution."""

    description: str = field(default="Creates execution plans and routes tasks deterministically", init=False)

    def __post_init__(self):
        """Create the planning agent."""
        self._node_agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            output_type=ExecutionPlan,
            name="create_execution_plan",
            retries=2,
        )

    @property
    def node_agent(self) -> Agent[StateDeps[SearchState], Any]:
        """Get the planning agent."""
        return self._node_agent

    @asynccontextmanager
    async def stream(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AsyncIterator[AgentStreamEvent]]:
        """Only streams when creating a plan (not when routing from queue)."""

        async def event_generator() -> AsyncIterator[AgentStreamEvent]:
            self.emit_node_active_event(ctx)
            # Streaming handled in _create_plan() method
            return
            yield

        yield event_generator()

    async def run(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> SearchNode | AggregationNode | ResultActionsNode | TextResponseNode | PlannerNode | End[str]:
        """Create plan or route to next task."""
        ctx.state.environment.record_node_entry(self.__class__.__name__)

        # Track if we're replanning after failure
        is_replanning_after_failure = bool(ctx.state.execution_plan and ctx.state.execution_plan.failed)

        # Clear failed plans
        if is_replanning_after_failure:
            logger.info("PlannerNode: Clearing failed plan")
            ctx.state.execution_plan = None

        # Case 1: Active plan with remaining tasks
        if ctx.state.execution_plan and not ctx.state.execution_plan.is_complete:
            return await self._execute_next_task(ctx)

        # Case 2: Completed plan - end execution
        if ctx.state.execution_plan and ctx.state.execution_plan.is_complete:
            logger.info("PlannerNode: Plan completed, ending execution")
            ctx.state.environment.complete_turn(
                assistant_answer="Complete",
            )
            ctx.state.execution_plan = None
            return End("Plan completed")

        # Case 3: No plan - create one
        return await self._create_and_execute_plan(ctx, is_replanning=is_replanning_after_failure)

    async def _create_and_execute_plan(
        self, ctx: GraphRunContext[SearchState, None], is_replanning: bool = False
    ) -> SearchNode | AggregationNode | ResultActionsNode | TextResponseNode | PlannerNode | End[str]:
        """Create plan via LLM."""
        logger.info("PlannerNode: Creating execution plan", is_replanning=is_replanning)

        # Get conversation history as message objects
        message_history = ctx.state.environment.get_message_history(max_turns=5, scope=MemoryScope.FULL)

        prompt = get_planning_prompt(ctx.state, is_replanning=is_replanning)

        if self.debug:
            log_agent_request(self.node_name, prompt, message_history)

        result = await self.node_agent.run(
            instructions=prompt, message_history=message_history, deps=StateDeps(ctx.state)
        )

        plan = result.output
        ctx.state.execution_plan = plan

        logger.info(
            "PlannerNode: Plan created",
            num_tasks=len(plan.tasks),
            tasks=[f"{i+1}. {t.reasoning}" for i, t in enumerate(plan.tasks)],
        )

        # Execute first task
        return await self._execute_next_task(ctx)

    async def _execute_next_task(
        self, ctx: GraphRunContext[SearchState, None]
    ) -> SearchNode | AggregationNode | ResultActionsNode | TextResponseNode | PlannerNode | End[str]:
        """Route to action node (NO LLM CALL - deterministic routing)."""
        plan = ctx.state.execution_plan
        if not plan:
            raise ValueError("_execute_next_task called without an execution plan")
        task = plan.current

        if not task:
            # All tasks complete
            logger.info("PlannerNode: All tasks completed")
            ctx.state.environment.complete_turn(
                assistant_answer="Complete",
            )
            ctx.state.execution_plan = None
            return End("Plan completed")

        logger.info(
            "PlannerNode: Routing to task",
            task_index=plan.current_index + 1,
            total_tasks=len(plan.tasks),
            action=task.action_type.value,
            reasoning=task.reasoning,
        )

        if self.debug:
            log_execution_plan(plan)

        task.status = TaskStatus.EXECUTING

        # Reset query for fresh search/aggregation tasks (prevents stale queries between tasks)
        if task.action_type in (TaskAction.SEARCH, TaskAction.AGGREGATION):
            ctx.state.query = None
            ctx.state.pending_filters = None

        # Deterministic routing based on task action_type
        if task.action_type == TaskAction.SEARCH:
            return SearchNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)
        if task.action_type == TaskAction.AGGREGATION:
            return AggregationNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)
        if task.action_type == TaskAction.RESULT_ACTIONS:
            return ResultActionsNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)
        if task.action_type == TaskAction.TEXT_RESPONSE:
            return TextResponseNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)
        logger.warning(f"Unknown task type: {task.action_type}, skipping")
        task.status = TaskStatus.COMPLETED
        plan.next()
        return PlannerNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)


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
        return get_search_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> PlannerNode | End[str]:
        ctx.state.environment.record_node_entry(self.__class__.__name__)

        try:
            if ctx.state.execution_plan and ctx.state.execution_plan.current:
                ctx.state.execution_plan.current.status = TaskStatus.COMPLETED
                ctx.state.execution_plan.next()

        except Exception as e:
            logger.error("SearchNode: Execution failed", error=str(e))

            if ctx.state.execution_plan and ctx.state.execution_plan.current:
                ctx.state.execution_plan.current.status = TaskStatus.FAILED

            ctx.state.environment.record_tool_step(
                ToolStep(step_type="error", description=f"Search failed: {str(e)}", success=False, error_message=str(e))
            )

            ctx.state.environment.complete_turn(
                assistant_answer=f"Search failed: {str(e)}",
            )
            return End(f"Failed: {str(e)}")

        return PlannerNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)


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
        return get_aggregation_execution_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> PlannerNode | End[str]:
        ctx.state.environment.record_node_entry(self.__class__.__name__)

        try:
            if ctx.state.execution_plan and ctx.state.execution_plan.current:
                ctx.state.execution_plan.current.status = TaskStatus.COMPLETED
                ctx.state.execution_plan.next()

        except Exception as e:
            logger.error("AggregationNode: Execution failed", error=str(e))

            if ctx.state.execution_plan and ctx.state.execution_plan.current:
                ctx.state.execution_plan.current.status = TaskStatus.FAILED

            ctx.state.environment.record_tool_step(
                ToolStep(
                    step_type="error", description=f"Aggregation failed: {str(e)}", success=False, error_message=str(e)
                )
            )

            ctx.state.environment.complete_turn(
                assistant_answer=f"Aggregation failed: {str(e)}",
            )
            return End(f"Failed: {str(e)}")

        return PlannerNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)


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
        return get_result_actions_prompt(ctx.state)

    def get_message_history(self, ctx: GraphRunContext[SearchState, None]):
        """ResultActionsNode only needs query_ids, not full queries."""
        return ctx.state.environment.get_message_history(max_turns=5, scope=MemoryScope.MINIMAL)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> PlannerNode | End[str]:
        ctx.state.environment.record_node_entry(self.__class__.__name__)

        try:
            if ctx.state.execution_plan and ctx.state.execution_plan.current:
                ctx.state.execution_plan.current.status = TaskStatus.COMPLETED
                ctx.state.execution_plan.next()

        except Exception as e:
            logger.error("ResultActionsNode: Execution failed", error=str(e))

            if ctx.state.execution_plan and ctx.state.execution_plan.current:
                ctx.state.execution_plan.current.status = TaskStatus.FAILED

            ctx.state.environment.record_tool_step(
                ToolStep(
                    step_type="error",
                    description=f"Result action failed: {str(e)}",
                    success=False,
                    error_message=str(e),
                )
            )

            ctx.state.environment.complete_turn(
                assistant_answer=f"Action failed: {str(e)}",
            )
            return End(f"Failed: {str(e)}")

        return PlannerNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)


@dataclass
class TextResponseNode(BaseGraphNode, BaseNode[SearchState, None, str]):
    """Generates text responses for general questions or out-of-scope queries.

    Handles TEXT_RESPONSE tasks where the user asks general questions, greetings,
    or requests that don't involve search/aggregation operations.
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
        return get_text_response_prompt(ctx.state)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> PlannerNode | End[str]:
        """Text response completes the flow."""
        ctx.state.environment.record_node_entry(self.__class__.__name__)

        if ctx.state.execution_plan and ctx.state.execution_plan.current:
            ctx.state.execution_plan.current.status = TaskStatus.COMPLETED
            ctx.state.execution_plan.next()

        return PlannerNode(model=self.model, event_emitter=self.event_emitter, debug=self.debug)


def emit_end_event(event_emitter: Callable[[BaseEvent], None] | None) -> None:
    """Emit GRAPH_NODE_ACTIVE event for End node."""
    if event_emitter:
        event_emitter(
            GraphNodeActiveEvent(
                timestamp=current_timestamp_ms(), value={"node": End.__name__, "step_type": "graph_node"}
            )
        )

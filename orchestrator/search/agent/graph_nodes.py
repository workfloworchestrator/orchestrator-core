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
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable

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
    TransitionEvent,
    TransitionValue,
)
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.tools import (
    execution_toolset,
    filter_building_toolset,
    query_analysis_toolset,
)
from orchestrator.search.core.types import ActionType
from orchestrator.search.query.queries import SelectQuery


def _current_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    from time import time_ns

    return time_ns() // 1_000_000


class StreamMixin:
    """Mixin to provide streaming functionality for graph nodes."""

    def get_node_name(self) -> str:
        """Get the name of this node for event emission."""
        return self.__class__.__name__  # type: ignore[attr-defined]

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str | None:
        """Get the prompt for the skill agent. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement get_prompt()")

    def get_toolsets(self) -> list[Any]:
        """Get the toolsets for this node. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement get_toolsets()")

    def cache_result(self, state_deps: StateDeps[SearchState], agent_run: Any) -> None:
        """Cache the result from streaming for use in run(). Override in subclasses if needed."""
        pass

    def create_next(self, node_class: type) -> Any:
        """Create next node with common parameters (search_agent, event_emitter).

        This ensures consistent node initialization and reduces brittleness.
        """
        return node_class(
            search_agent=self.search_agent,  # type: ignore[attr-defined]
            event_emitter=self.event_emitter,  # type: ignore[attr-defined]
        )

    async def event_generator(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AgentStreamEvent]:
        """Generate events from the search agent as they happen."""
        # Emit GRAPH_NODE_ENTER event at the start
        if hasattr(self, "event_emitter") and self.event_emitter:  # type: ignore[attr-defined]
            value: GraphNodeEnterValue = {"node": self.get_node_name(), "step_type": "graph_node"}
            graph_event = GraphNodeEnterEvent(timestamp=_current_timestamp_ms(), value=value)
            await self.event_emitter(graph_event)  # type: ignore[attr-defined]

        prompt = self.get_prompt(ctx)
        if prompt is None:
            return  # No prompt means no agent call

        state_deps = StateDeps(ctx.state.model_copy())
        toolsets = self.get_toolsets()

        async with self.search_agent.iter(user_prompt=prompt, deps=state_deps, toolsets=toolsets) as agent_run:  # type: ignore[attr-defined]
            async for agent_node in agent_run:
                if Agent.is_end_node(agent_node):
                    self.cache_result(state_deps, agent_run)
                elif Agent.is_model_request_node(agent_node):
                    async with agent_node.stream(agent_run.ctx) as event_stream:  # type: ignore[union-attr]
                        async for stream_event in event_stream:
                            yield stream_event

    async def emit_transition_events(self) -> None:
        """Emit graph transition events after determining next node.

        This is called after cache_result() has determined the next node.
        Subclasses that need to emit transition events should override this.
        """
        pass

    @asynccontextmanager
    async def stream(self, ctx: GraphRunContext[SearchState, None]) -> AsyncIterator[AsyncIterator[AgentStreamEvent]]:
        """Stream events from the skill agent in real-time."""
        yield self.event_generator(ctx)
        # After streaming completes, emit transition events
        # cache_result() has already been called and determined the next node
        await self.emit_transition_events()


logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    # For type checking, Agent is generic
    SkillAgent = Agent[StateDeps["SearchState"], str]
else:
    # At runtime, Agent is not parameterized
    SkillAgent = Agent


@dataclass
class QueryAnalysisNode(StreamMixin, BaseNode[SearchState, None, str]):
    """Analyzes user input to determine query type and entity.

    This node uses a skill agent to:
    - Analyze the user's intent
    - Determine entity_type and action (SELECT/COUNT/AGGREGATE)
    - Call start_new_search tool to initialize the query
    """

    user_input: str
    search_agent: SkillAgent
    event_emitter: Callable[[BaseEvent], Awaitable[None]] | None = None
    _final_state: SearchState | None = field(default=None, init=False)
    _next_node: FilterBuildingNode | ExecutionNode | None = field(default=None, init=False)
    _next_node_name: str | None = field(default=None, init=False)
    _decision: str | None = field(default=None, init=False)

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the prompt for query analysis."""
        return f"""Call start_new_search for: "{self.user_input}"

entity_type: SUBSCRIPTION|PRODUCT|WORKFLOW|PROCESS
action: select|count|aggregate

After calling start_new_search, return True."""

    def get_toolsets(self) -> list[Any]:
        """Get toolsets for query analysis node."""
        return [query_analysis_toolset]

    def cache_result(self, state_deps: StateDeps[SearchState], agent_run: Any) -> None:
        """Cache the state from streaming and determine next node."""
        self._final_state = state_deps.state

        # Determine next node early so we can emit transition events at the right time
        needs_filters = self._needs_filters(state_deps.state)
        if needs_filters:
            self._next_node = self.create_next(FilterBuildingNode)
            self._next_node_name = "FilterBuildingNode"
            self._decision = "Filters are needed based on query analysis"
        else:
            self._next_node = self.create_next(ExecutionNode)
            self._next_node_name = "ExecutionNode"
            self._decision = "No filters needed, proceeding directly to execution"

    async def emit_transition_events(self) -> None:
        """Emit PATH_SELECTED and EXIT events after streaming completes."""
        if self.event_emitter and self._next_node_name and self._decision:
            path_value: TransitionValue = {
                "node": "QueryAnalysisNode",
                "to_node": self._next_node_name,
                "decision": self._decision,
            }
            path_event = TransitionEvent(timestamp=_current_timestamp_ms(), value=path_value)
            await self.event_emitter(path_event)

            exit_value: GraphNodeExitValue = {"node": "QueryAnalysisNode", "next_node": self._next_node_name}
            exit_event = GraphNodeExitEvent(timestamp=_current_timestamp_ms(), value=exit_value)
            await self.event_emitter(exit_event)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> FilterBuildingNode | ExecutionNode:
        """Analyze user input and initialize search context.

        Returns:
            FilterBuildingNode if filters are needed, otherwise ExecutionNode
        """
        logger.debug("QueryAnalysisNode: Analyzing user input", user_input=self.user_input)

        # If stream() was called, use the cached state; otherwise run the agent
        if self._final_state is not None:
            updated_state = self._final_state
            logger.debug("QueryAnalysisNode: Using cached state from streaming")
        else:
            state_deps = StateDeps(ctx.state.model_copy())
            prompt = f"""Call start_new_search for: "{self.user_input}"

entity_type: SUBSCRIPTION|PRODUCT|WORKFLOW|PROCESS
action: select|count|aggregate"""

            try:
                await self.search_agent.run(user_prompt=prompt, deps=state_deps, toolsets=[query_analysis_toolset])

                # Verify that start_new_search was actually called by checking if state was updated
                if state_deps.state.query is None or state_deps.state.action is None:
                    logger.warning(
                        "QueryAnalysisNode: start_new_search may not have been called",
                        user_input=self.user_input,
                        has_query=state_deps.state.query is not None,
                        has_action=state_deps.state.action is not None,
                    )
                    # The state should have been updated by the tool, if not, something went wrong
                    raise ValueError("start_new_search tool was not called or did not update state")

            except Exception as e:
                logger.error(
                    "QueryAnalysisNode: Failed to call start_new_search",
                    error=str(e),
                    error_type=type(e).__name__,
                    user_input=self.user_input,
                )
                # Re-raise the exception - let the graph handle it
                raise

            updated_state = state_deps.state
        ctx.state = updated_state

        # If we already determined next node during streaming, use it
        if self._next_node is not None:
            logger.debug("QueryAnalysisNode: Using cached next node from streaming")
            return self._next_node

        # Otherwise determine it now (fallback for non-streaming path)
        needs_filters = self._needs_filters(updated_state)

        logger.debug(
            "QueryAnalysisNode: Analysis complete",
            action=updated_state.action,
            has_query=updated_state.query is not None,
            needs_filters=needs_filters,
        )

        if needs_filters:
            next_node: FilterBuildingNode | ExecutionNode = self.create_next(FilterBuildingNode)
        else:
            next_node = self.create_next(ExecutionNode)

        return next_node

    def _needs_filters(self, state: SearchState) -> bool:
        """Determine if filters are needed based on the query."""
        if not state.query:
            return False

        if isinstance(state.query, SelectQuery):
            if state.query.query_text:
                filter_keywords = ["where", "with", "that", "filter", "only", "except"]
                query_lower = state.query.query_text.lower()
                if any(keyword in query_lower for keyword in filter_keywords):
                    return state.query.filters is None  # Need filters if not already set
        return False


@dataclass
class FilterBuildingNode(StreamMixin, BaseNode[SearchState, None, str]):
    """Builds filter tree if needed.

    This node uses a skill agent to:
    - Discover filter paths
    - Get valid operators
    - Build and set the filter tree
    """

    search_agent: SkillAgent
    event_emitter: Callable[[BaseEvent], Awaitable[None]] | None = None
    _final_state: SearchState | None = field(default=None, init=False)
    _next_node: ExecutionNode | None = field(default=None, init=False)

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the prompt for filter building."""
        return "Build filters: discover paths, get operators, call set_filter_tree. Then return True."

    def get_toolsets(self) -> list[Any]:
        """Get toolsets for filter building node."""
        return [filter_building_toolset]

    def cache_result(self, state_deps: StateDeps[SearchState], agent_run: Any) -> None:
        """Cache the state from streaming."""
        self._final_state = state_deps.state
        # Always go to ExecutionNode after building filters
        self._next_node = self.create_next(ExecutionNode)

    async def emit_transition_events(self) -> None:
        """Emit PATH_SELECTED and EXIT events after streaming completes."""
        if self.event_emitter and self._next_node:
            next_node_name = self._next_node.get_node_name()
            path_value: TransitionValue = {
                "node": "FilterBuildingNode",
                "to_node": next_node_name,
                "decision": "Filters built, proceeding to execution",
            }
            path_event = TransitionEvent(timestamp=_current_timestamp_ms(), value=path_value)
            await self.event_emitter(path_event)

            exit_value: GraphNodeExitValue = {"node": "FilterBuildingNode", "next_node": next_node_name}
            exit_event = GraphNodeExitEvent(timestamp=_current_timestamp_ms(), value=exit_value)
            await self.event_emitter(exit_event)

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> ExecutionNode:
        """Build filters using skill agent.

        The skill agent will call:
        - discover_filter_paths
        - get_valid_operators
        - set_filter_tree
        """
        logger.debug("FilterBuildingNode: Building filters", query=ctx.state.query)

        # If stream() was called, use the cached state; otherwise run the agent
        if self._final_state is not None:
            ctx.state = self._final_state
            logger.debug("FilterBuildingNode: Using cached state from streaming")
        else:
            state_deps = StateDeps(ctx.state.model_copy())
            await self.search_agent.run(
                user_prompt="Build filters: discover paths, get operators, call set_filter_tree.",
                deps=state_deps,
                toolsets=[filter_building_toolset],
            )

            ctx.state = state_deps.state

        logger.debug(
            "FilterBuildingNode: Filters built",
            has_filters=ctx.state.query.filters is not None if ctx.state.query else False,
        )

        # If we already determined next node during streaming, use it
        if self._next_node is not None:
            logger.debug("FilterBuildingNode: Using cached next node from streaming")
            return self._next_node

        # Otherwise create it now (fallback for non-streaming path)
        return self.create_next(ExecutionNode)


@dataclass
class ExecutionNode(StreamMixin, BaseNode[SearchState, None, str]):
    """Executes search or aggregation.

    This node uses a skill agent to:
    - Execute run_search for SELECT actions
    - Execute run_aggregation for COUNT/AGGREGATE actions
    """

    search_agent: SkillAgent
    event_emitter: Callable[[BaseEvent], Awaitable[None]] | None = None
    _agent_executed: bool = field(default=False, init=False)
    _next_node: ResultProcessingNode | ResponseNode | None = field(default=None, init=False)
    _decision: str | None = field(default=None, init=False)

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str | None:
        """Get the prompt for execution based on action type."""
        action = ctx.state.action
        if action == ActionType.SELECT:
            return "Execute the search by calling run_search()."
        if action in (ActionType.COUNT, ActionType.AGGREGATE):
            return "Execute the aggregation by calling run_aggregation()."
        return None  # No agent call for unknown action

    def get_toolsets(self) -> list[Any]:
        """Get toolsets for execution node."""
        return [execution_toolset]

    def cache_result(self, state_deps: StateDeps[SearchState], agent_run: Any) -> None:
        """Mark that agent was executed."""
        self._agent_executed = True

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> ResultProcessingNode | ResponseNode:
        """Execute search or aggregation based on action type."""
        action = ctx.state.action
        logger.debug("ExecutionNode: Executing", action=action)

        # If stream() was called, skip the agent call; otherwise run the agent
        if not self._agent_executed:
            if action == ActionType.SELECT:
                await self.search_agent.run(
                    user_prompt="Execute the search by calling run_search().",
                    deps=StateDeps(ctx.state),
                    toolsets=[execution_toolset],
                )
            elif action in (ActionType.COUNT, ActionType.AGGREGATE):
                await self.search_agent.run(
                    user_prompt="Execute the aggregation by calling run_aggregation().",
                    deps=StateDeps(ctx.state),
                    toolsets=[execution_toolset],
                )
            else:
                logger.warning("ExecutionNode: Unknown action type", action=action)
        else:
            logger.debug("ExecutionNode: Using cached execution from streaming")

        needs_processing = self._needs_result_processing(ctx.state)

        logger.debug(
            "ExecutionNode: Execution complete",
            results_count=ctx.state.results_count,
            needs_processing=needs_processing,
        )

        # Determine next node and emit events
        if needs_processing:
            next_node: ResultProcessingNode | ResponseNode = self.create_next(ResultProcessingNode)
            decision = "Result processing needed (details/export)"
        else:
            next_node = self.create_next(ResponseNode)
            decision = "No result processing needed, proceeding to response"

        if self.event_emitter:
            next_node_name = next_node.get_node_name()
            path_value: TransitionValue = {
                "node": "ExecutionNode",
                "to_node": next_node_name,
                "decision": decision,
            }
            path_event = TransitionEvent(timestamp=_current_timestamp_ms(), value=path_value)
            await self.event_emitter(path_event)

            exit_value: GraphNodeExitValue = {"node": "ExecutionNode", "next_node": next_node_name}
            exit_event = GraphNodeExitEvent(timestamp=_current_timestamp_ms(), value=exit_value)
            await self.event_emitter(exit_event)

        return next_node

    def _needs_result_processing(self, state: SearchState) -> bool:
        """Determine if result processing (details/export) is needed."""
        return False


@dataclass
class ResultProcessingNode(StreamMixin, BaseNode[SearchState, None, str]):
    """Processes results (fetch details, export, etc.).

    This node uses a skill agent to:
    - Fetch entity details if needed
    - Prepare export if requested
    """

    search_agent: SkillAgent
    event_emitter: Callable[[BaseEvent], Awaitable[None]] | None = None
    _final_state: SearchState | None = field(default=None, init=False)

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the prompt for result processing."""
        return "Process results: call fetch_entity_details or prepare_export if needed."

    def get_toolsets(self) -> list[Any]:
        """Get toolsets for result processing node - uses search_toolset for fetch_entity_details and prepare_export."""
        from orchestrator.search.agent.tools import search_toolset

        return [search_toolset]

    def cache_result(self, state_deps: StateDeps[SearchState], agent_run: Any) -> None:
        """Cache the state from streaming."""
        self._final_state = state_deps.state

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> ResponseNode:
        """Process results using skill agent.

        The skill agent will call:
        - fetch_entity_details if details are needed
        - prepare_export if export is requested
        """
        logger.debug("ResultProcessingNode: Processing results", results_count=ctx.state.results_count)

        # If stream() was called, use the cached state; otherwise run the agent
        if self._final_state is not None:
            ctx.state = self._final_state
            logger.debug("ResultProcessingNode: Using cached state from streaming")
        else:
            from orchestrator.search.agent.tools import search_toolset

            state_deps = StateDeps(ctx.state.model_copy())
            await self.search_agent.run(
                user_prompt="Process results: call fetch_entity_details or prepare_export if needed.",
                deps=state_deps,
                toolsets=[search_toolset],
            )

            ctx.state = state_deps.state

        logger.debug("ResultProcessingNode: Results processed")

        next_node = self.create_next(ResponseNode)

        if self.event_emitter:
            next_node_name = next_node.get_node_name()
            path_value: TransitionValue = {
                "node": "ResultProcessingNode",
                "to_node": next_node_name,
                "decision": "Results processed, proceeding to response",
            }
            path_event = TransitionEvent(timestamp=_current_timestamp_ms(), value=path_value)
            await self.event_emitter(path_event)

            exit_value: GraphNodeExitValue = {"node": "ResultProcessingNode", "next_node": next_node_name}
            exit_event = GraphNodeExitEvent(timestamp=_current_timestamp_ms(), value=exit_value)
            await self.event_emitter(exit_event)

        return next_node


@dataclass
class ResponseNode(StreamMixin, BaseNode[SearchState, None, str]):
    """Generates final response to the user.

    This node uses a skill agent to generate a natural language response
    based on the search results and state.
    """

    search_agent: SkillAgent
    event_emitter: Callable[[BaseEvent], Awaitable[None]] | None = None
    _final_output: str | None = field(default=None, init=False)

    def get_prompt(self, ctx: GraphRunContext[SearchState, None]) -> str:
        """Get the prompt for response generation."""
        return "Generate a concise response summarizing the results."

    def get_toolsets(self) -> list[Any]:
        """Get toolsets for response node - no tools needed, just text generation."""
        return []

    def cache_result(self, state_deps: StateDeps[SearchState], agent_run: Any) -> None:
        """Cache the output from streaming."""
        if agent_run.result is not None:
            self._final_output = (
                agent_run.result.output if hasattr(agent_run.result, "output") else str(agent_run.result)
            )

    async def run(self, ctx: GraphRunContext[SearchState, None]) -> End[str]:
        """Generate final response using skill agent."""
        logger.debug("ResponseNode: Generating response", results_count=ctx.state.results_count)

        # If stream() was called, use the cached output; otherwise run the agent
        if self._final_output is not None:
            output = self._final_output
            logger.debug("ResponseNode: Using cached output from streaming")
        else:
            state_deps = StateDeps(ctx.state.model_copy())
            result = await self.search_agent.run(
                user_prompt="Generate a concise response summarizing the results.",
                deps=state_deps,
                toolsets=[],
            )
            output = result.output

        logger.info("ResponseNode: Response generated", response_output=output)

        if self.event_emitter:
            exit_value: GraphNodeExitValue = {"node": "ResponseNode", "next_node": None}
            exit_event = GraphNodeExitEvent(timestamp=_current_timestamp_ms(), value=exit_value)
            await self.event_emitter(exit_event)

        return End(output)

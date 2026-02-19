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

from collections import deque
from typing import TYPE_CHECKING, Any, AsyncIterator, Sequence

import structlog
from pydantic_ai import Agent, AgentRunResult, ModelSettings
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import (
    AgentStreamEvent,
    UserContent,
)
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset
from pydantic_graph import End, Graph, GraphRunContext

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model
else:
    KnownModelName = str
    Model = Any

from orchestrator.search.agent.graph_nodes import (
    ACTION_TO_NODE,
    AggregationNode,
    PlannerNode,
    ResultActionsNode,
    SearchNode,
    TextResponseNode,
    emit_end_event,
)
from orchestrator.search.agent.schemas import GraphEdge, GraphNode, GraphStructure
from orchestrator.search.agent.skills import SKILLS, Skill
from orchestrator.search.agent.state import SearchState, TaskAction

logger = structlog.get_logger(__name__)


class GraphAgentAdapter(Agent[StateDeps[SearchState], str]):
    """Adapter that overrides run_stream_events to execute a pydantic-graph instead of standard Agent behavior.

    Implements the Agent interface for AG-UI compatibility while replacing LLM conversation
    with multi-node graph execution. The model/toolsets are required by Agent's constructor
    but unused - the search_agent in graph nodes handles actual LLM calls.
    """

    DEFAULT_START_NODE = PlannerNode

    def __init__(
        self,
        model: "Model | KnownModelName | str",  # type: ignore[valid-type]
        graph: Graph[SearchState, None, str],
        skills: dict[TaskAction, Skill],
        *,
        deps_type: type[StateDeps[SearchState]] = StateDeps[SearchState],
        model_settings: "ModelSettings | None" = None,
        toolsets: Sequence[AbstractToolset[Any]] | None = None,
        instructions: Any = None,
        debug: bool = False,
    ):
        """Initialize the graph wrapper agent.

        Args:
            model: LLM model to use (stored for node creation)
            graph: The pydantic-graph Graph instance to execute
            skills: Skill definitions keyed by TaskAction
            deps_type: Dependencies type (defaults to StateDeps[SearchState])
            model_settings: Model settings
            toolsets: Tool sets (not used directly, but required by base class)
            instructions: Instructions (not used directly, but required by base class)
            debug: Enable debug logging for all nodes
        """
        super().__init__(
            model=model,
            deps_type=deps_type,
            model_settings=model_settings or ModelSettings(),
            toolsets=toolsets or [],
            instructions=instructions or [],
        )
        self.graph = graph
        self.skills = skills
        self.model_name = model if isinstance(model, str) else str(model)
        self._persistence: Any | None = None
        self.debug = debug

    def get_graph_structure(self) -> GraphStructure:
        """Build graph structure for visualization.

        Returns:
            GraphStructure with nodes, edges, and start_node
        """
        # Build nodes
        nodes = []
        for node_id, node_def in self.graph.node_defs.items():
            # Get the node class from NodeDef
            node_class = node_def.node
            description = None
            if hasattr(node_class, "__dataclass_fields__"):
                fields = node_class.__dataclass_fields__
                if "description" in fields:
                    description = fields["description"].default

            nodes.append(
                GraphNode(
                    id=node_id,
                    label=node_id,
                    description=description,
                )
            )

        # Build edges - only from PlannerNode to action nodes
        # Skip edges from action nodes back to PlannerNode to avoid visual clutter
        edges = []
        for node_id, node_def in self.graph.node_defs.items():
            if node_id == PlannerNode.__name__:
                for next_node_id, edge in node_def.next_node_edges.items():
                    edges.append(GraphEdge(source=node_id, target=next_node_id, label=getattr(edge, "label", None)))

        return GraphStructure(nodes=nodes, edges=edges, start_node=self.DEFAULT_START_NODE.__name__)

    async def run_stream_events(  # type: ignore[override]
        self,
        user_prompt: str | Sequence[UserContent] | None = None,
        *,
        deps: StateDeps[SearchState] | None = None,
        target_action: TaskAction | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[AgentStreamEvent | AgentRunResultEvent[str] | Any]:
        """Execute the graph and stream events in real-time.

        This implementation manually streams events because for now pydantic-ai only supports
        emitting events from tool calls. Since we need to emit custom graph
        events (node transitions, state changes), we cannot use the standard AG-UI
        handlers (handle_ag_ui_request, AGUIAdapter.dispatch_request) as they filter
        out custom events via pattern matching in UIEventStream.handle_event().

        The pattern:
        1. graph.iter() or graph.iter_from_persistence() yields the next node to execute
        2. Call node.stream(ctx) to get an async generator of AgentStreamEvents
        3. Yield those events in real-time to the frontend
        4. Continue until End node is reached

        Args:
            user_prompt: User input (not used - comes from deps.state.user_input)
            deps: StateDeps containing SearchState
            persistence: PostgresStatePersistence for resuming interrupted graphs
            **kwargs: Additional arguments
        """
        if deps is None:
            deps = StateDeps(SearchState())

        initial_state = deps.state

        # Get user input from state (populated by endpoint from run_input.messages via AG-UI)
        user_input = initial_state.user_input

        try:
            self._current_graph_events: deque[str] = deque()

            def emit_event(event):
                self._current_graph_events.append(f"data: {event.model_dump_json()}\n\n")

            persistence = self._persistence
            # If persistence provided, try to load previous state
            if persistence:
                snapshot = await persistence.load_next()
                if snapshot:
                    previous_state = snapshot.state
                    logger.debug(
                        "GraphAgentAdapter: Resuming from previous state",
                        run_id=persistence.run_id,
                    )
                    # Use the loaded state as initial state, but update user_input for current turn
                    initial_state = previous_state
                    initial_state.user_input = user_input  # Update with current turn's input

            if (
                not initial_state.environment.current_turn
                or initial_state.environment.current_turn.user_question != user_input
            ):
                initial_state.environment.start_turn(user_input)

            if target_action:
                node_cls = ACTION_TO_NODE[target_action]
                start_node = node_cls(
                    model=self.model_name,
                    skills=self.skills,
                    event_emitter=emit_event,
                    debug=self.debug,
                )
            else:
                start_node = self.DEFAULT_START_NODE(
                    model=self.model_name,
                    skills=self.skills,
                    event_emitter=emit_event,
                    debug=self.debug,
                )

            logger.debug("GraphAgentAdapter: Starting new graph execution", node=type(start_node).__name__)

            async with self.graph.iter(
                start_node=start_node, state=initial_state, persistence=persistence  # type: ignore[arg-type]
            ) as graph_run:
                async for next_node in graph_run:

                    if isinstance(next_node, End):
                        emit_end_event(emit_event)
                        break

                    # Stream events from the node
                    ctx = GraphRunContext(state=graph_run.state, deps=graph_run.deps)
                    async with next_node.stream(ctx) as event_stream:  # type: ignore[attr-defined]
                        async for event in event_stream:
                            yield event

                final_output = (
                    str(getattr(graph_run.result, "output", graph_run.result))
                    if graph_run.result
                    else "Graph execution completed"
                )

                deps.state = graph_run.state

                # complete_turn() is now called by nodes before returning End()
                # This ensures the automatic snapshot_end() captures the completed turn

            logger.debug(
                "GraphAgentAdapter: Graph streaming complete",
                final_output=final_output,
                final_state_keys=list(graph_run.state.model_dump().keys()),
            )

            yield AgentRunResultEvent(result=AgentRunResult(output=final_output))

        except Exception as e:
            logger.error("GraphAgentAdapter: Graph streaming failed", error=str(e), exc_info=True)
            raise


def build_agent_instance(
    model: str, agent_tools: list[FunctionToolset[Any]] | None = None, debug: bool = False
) -> GraphAgentAdapter:
    """Build and configure the graph-based search agent instance.

    Args:
        model: The LLM model to use (string or model instance)
        agent_tools: Optional list of additional toolsets to include (currently unused)
        debug: Enable debug logging for all graph nodes

    Returns:
        GraphAgentAdapter instance
    """
    graph: Graph[SearchState, None, str] = Graph(
        nodes=[
            PlannerNode,
            SearchNode,
            AggregationNode,
            ResultActionsNode,
            TextResponseNode,
        ],
    )

    adapter = GraphAgentAdapter(
        model=model,
        graph=graph,
        skills=SKILLS,
        deps_type=StateDeps[SearchState],
        debug=debug,
    )

    logger.debug("GraphAgentAdapter: Built graph-based agent adapter", model=model)

    return adapter

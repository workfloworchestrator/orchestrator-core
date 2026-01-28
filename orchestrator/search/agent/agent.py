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
    NODE_DESCRIPTIONS,
    AggregationNode,
    FilterBuildingNode,
    IntentNode,
    SearchNode,
    TextResponseNode,
    emit_end_event,
)
from orchestrator.search.agent.schemas import GraphEdge, GraphNode, GraphStructure
from orchestrator.search.agent.state import SearchState

logger = structlog.get_logger(__name__)


class GraphAgentAdapter(Agent[StateDeps[SearchState], str]):
    """Adapter that overrides run_stream_events to execute a pydantic-graph instead of standard Agent behavior.

    Implements the Agent interface for AG-UI compatibility while replacing LLM conversation
    with multi-node graph execution. The model/toolsets are required by Agent's constructor
    but unused - the search_agent in graph nodes handles actual LLM calls.
    """

    DEFAULT_START_NODE = IntentNode

    def __init__(
        self,
        model: "Model | KnownModelName | str",  # type: ignore[valid-type]
        graph: Graph[SearchState, None, str],
        *,
        deps_type: type[StateDeps[SearchState]] = StateDeps[SearchState],
        model_settings: "ModelSettings | None" = None,
        toolsets: Sequence[AbstractToolset[Any]] | None = None,
        instructions: Any = None,
    ):
        """Initialize the graph wrapper agent.

        Args:
            model: LLM model to use (stored for node creation)
            graph: The pydantic-graph Graph instance to execute
            deps_type: Dependencies type (defaults to StateDeps[SearchState])
            model_settings: Model settings
            toolsets: Tool sets (not used directly, but required by base class)
            instructions: Instructions (not used directly, but required by base class)
        """
        super().__init__(
            model=model,
            deps_type=deps_type,
            model_settings=model_settings or ModelSettings(),
            toolsets=toolsets or [],
            instructions=instructions or [],
        )
        self.graph = graph
        self.model_name = model if isinstance(model, str) else str(model)

    def get_graph_structure(self) -> GraphStructure:
        """Build graph structure for visualization.

        Returns:
            GraphStructure with nodes, edges, and start_node
        """
        # Build nodes
        nodes = [
            GraphNode(
                id=node_id,
                label=node_id,
                description=NODE_DESCRIPTIONS.get(node_id),
            )
            for node_id, node_def in self.graph.node_defs.items()
        ]

        # TODO: Fix dynamic build: hardcoded based on routing logic
        # since pydantic-graph uses dynamic routing based on node outputs.
        edges = [
            # From IntentNode
            GraphEdge(source=IntentNode.__name__, target=SearchNode.__name__),
            GraphEdge(source=IntentNode.__name__, target=AggregationNode.__name__),
            GraphEdge(source=IntentNode.__name__, target=FilterBuildingNode.__name__),
            GraphEdge(source=IntentNode.__name__, target=TextResponseNode.__name__),
            # From FilterBuildingNode
            GraphEdge(source=FilterBuildingNode.__name__, target=SearchNode.__name__),
            GraphEdge(source=FilterBuildingNode.__name__, target=AggregationNode.__name__),
            # From SearchNode
            GraphEdge(source=SearchNode.__name__, target=TextResponseNode.__name__),
            # From AggregationNode
            GraphEdge(source=AggregationNode.__name__, target=TextResponseNode.__name__),
            # From TextResponseNode to End
            GraphEdge(source=TextResponseNode.__name__, target=End.__name__),
        ]

        # Add End node for visualization
        nodes.append(GraphNode(id=End.__name__, label="End", description="Graph execution complete"))

        return GraphStructure(nodes=nodes, edges=edges, start_node=self.DEFAULT_START_NODE.__name__)

    async def run_stream_events(  # type: ignore[override]
        self,
        user_prompt: str | Sequence[UserContent] | None = None,
        *,
        deps: StateDeps[SearchState] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[AgentStreamEvent | AgentRunResultEvent[str] | Any]:
        """Execute the graph and stream events in real-time.

        This implementation manually streams events because for now pydantic-ai only supports
        emitting events from tool calls. Since we need to emit custom graph
        events (node transitions, state changes), we cannot use the standard AG-UI
        handlers (handle_ag_ui_request, AGUIAdapter.dispatch_request) as they filter
        out custom events via pattern matching in UIEventStream.handle_event().

        The pattern:
        1. graph.iter() yields the next node to execute (determined by previous node's result)
        2. Call node.stream(ctx) to get an async generator of AgentStreamEvents
        3. Yield those events in real-time to the frontend
        4. Continue until End node is reached
        """
        if deps is None:
            deps = StateDeps(SearchState())

        initial_state = deps.state

        # Get user input from state (populated by endpoint from run_input.messages via AG-UI)
        user_input = initial_state.user_input

        try:
            self._current_graph_events: deque[str] = deque()
            emit_event = lambda event: self._current_graph_events.append(f"data: {event.model_dump_json()}\n\n")

            start_node = self.DEFAULT_START_NODE(
                user_input=user_input,
                model=self.model_name,
                event_emitter=emit_event,
            )

            logger.debug("GraphAgentAdapter: Starting graph streaming", node=type(start_node).__name__)

            async with self.graph.iter(start_node=start_node, state=initial_state) as graph_run:
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

            logger.info("GraphAgentAdapter: Graph streaming complete", final_output=final_output)
            yield AgentRunResultEvent(result=AgentRunResult(output=final_output))

        except Exception as e:
            logger.error("GraphAgentAdapter: Graph streaming failed", error=str(e), exc_info=True)
            raise


def build_agent_instance(model: str, agent_tools: list[FunctionToolset[Any]] | None = None) -> GraphAgentAdapter:
    """Build and configure the graph-based search agent instance.

    Args:
        model: The LLM model to use (string or model instance)
        agent_tools: Optional list of additional toolsets to include (currently unused)

    Returns:
        GraphAgentAdapter instance
    """
    graph: Graph[SearchState, None, str] = Graph(
        nodes=[
            IntentNode,
            FilterBuildingNode,
            SearchNode,
            AggregationNode,
            TextResponseNode,
        ],
    )

    adapter = GraphAgentAdapter(
        model=model,
        graph=graph,
        deps_type=StateDeps[SearchState],
    )

    logger.debug("GraphAgentAdapter: Built graph-based agent adapter", model=model)

    return adapter

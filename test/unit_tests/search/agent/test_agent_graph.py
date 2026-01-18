from unittest.mock import MagicMock

import pytest
from pydantic_ai import Agent
from pydantic_graph import GraphRunContext

from orchestrator.search.agent.graph_events import GraphNodeExitEvent
from orchestrator.search.agent.graph_nodes import (
    ExecutionNode,
    FilterBuildingNode,
    QueryAnalysisNode,
    ResponseNode,
)
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.tools import (
    execution_toolset,
    filter_building_toolset,
    query_analysis_toolset,
)
from orchestrator.search.core.types import ActionType, EntityType
from orchestrator.search.query.queries import CountQuery


@pytest.mark.asyncio
async def test_graph_event_sequence():
    """Test that graph events are emitted in correct sequence during node transitions."""
    emitted_events = []

    async def event_emitter(event):
        emitted_events.append(event)

    mock_agent = MagicMock(spec=Agent)

    query_node = QueryAnalysisNode(
        user_input="count subscriptions",
        search_agent=mock_agent,
        event_emitter=event_emitter,
    )
    execution_node = ExecutionNode(search_agent=mock_agent, event_emitter=event_emitter)
    response_node = ResponseNode(search_agent=mock_agent, event_emitter=event_emitter)

    # Test QueryAnalysisNode exit event
    await query_node._emit_exit(FilterBuildingNode.__name__, "Query analysis complete")

    # Test ExecutionNode exit event
    ctx = GraphRunContext(
        state=SearchState(action=ActionType.COUNT, query=CountQuery(entity_type=EntityType.SUBSCRIPTION)),
        deps=None,
    )
    ctx.state.results_count = 42
    await execution_node._emit_exit(ResponseNode.__name__, "Execution complete")

    # Test ResponseNode exit event (terminal node)
    await response_node._emit_exit(None, "Response generation complete")

    # Verify event sequence
    assert len(emitted_events) == 3
    assert isinstance(emitted_events[0], GraphNodeExitEvent)  # QueryAnalysisNode exit
    assert isinstance(emitted_events[1], GraphNodeExitEvent)  # ExecutionNode exit
    assert isinstance(emitted_events[2], GraphNodeExitEvent)  # ResponseNode exit (terminal)

    # Verify correct node flow and decisions
    assert emitted_events[0].value["node"] == QueryAnalysisNode.__name__
    assert emitted_events[0].value["next_node"] == FilterBuildingNode.__name__
    assert emitted_events[0].value["decision"] == "Query analysis complete"

    assert emitted_events[1].value["node"] == ExecutionNode.__name__
    assert emitted_events[1].value["next_node"] == ResponseNode.__name__
    assert emitted_events[1].value["decision"] == "Execution complete"

    assert emitted_events[2].value["node"] == ResponseNode.__name__
    assert emitted_events[2].value["next_node"] is None  # Terminal node
    assert emitted_events[2].value["decision"] == "Response generation complete"


@pytest.mark.asyncio
async def test_node_toolsets_are_isolated():
    """Test that each node only has access to its specific toolset."""
    mock_agent = MagicMock(spec=Agent)

    query_node = QueryAnalysisNode(
        user_input="count subscriptions",
        search_agent=mock_agent,
        event_emitter=None,
    )
    filter_node = FilterBuildingNode(search_agent=mock_agent, event_emitter=None)
    execution_node = ExecutionNode(search_agent=mock_agent, event_emitter=None)

    # Verify each node returns ONLY its specific toolset
    query_toolsets = query_node.toolsets
    assert len(query_toolsets) == 1
    assert query_toolsets[0] is query_analysis_toolset

    filter_toolsets = filter_node.toolsets
    assert len(filter_toolsets) == 1
    assert filter_toolsets[0] is filter_building_toolset

    execution_toolsets = execution_node.toolsets
    assert len(execution_toolsets) == 1
    assert execution_toolsets[0] is execution_toolset

    # Verify they are different toolsets (no sharing)
    assert query_toolsets[0] is not filter_toolsets[0]
    assert query_toolsets[0] is not execution_toolsets[0]
    assert filter_toolsets[0] is not execution_toolsets[0]

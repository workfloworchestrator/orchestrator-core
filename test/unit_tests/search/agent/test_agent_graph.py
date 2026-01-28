from unittest.mock import MagicMock

import pytest
from pydantic_ai import Agent

from orchestrator.search.agent.graph_events import GraphNodeExitEvent
from orchestrator.search.agent.graph_nodes import (
    FilterBuildingNode,
    IntentNode,
    SearchNode,
    TextResponseNode,
)


@pytest.mark.asyncio
async def test_graph_event_sequence():
    """Test that graph events are emitted in correct sequence during node transitions."""
    emitted_events = []

    async def event_emitter(event):
        emitted_events.append(event)

    mock_agent = MagicMock(spec=Agent)  # type: ignore[var-annotated]
    agents: dict = {"filter_building_agent": mock_agent, "search_agent": mock_agent, "text_response_agent": mock_agent}

    intent_node = IntentNode(
        user_input="count subscriptions",
        node_agent=mock_agent,
        intent_agent=mock_agent,
        query_init_agent=mock_agent,
        agents=agents,
        event_emitter=event_emitter,
    )
    search_node = SearchNode(node_agent=mock_agent, agents=agents, event_emitter=event_emitter)
    text_response_node = TextResponseNode(node_agent=mock_agent, event_emitter=event_emitter)

    # Test IntentNode exit event
    await intent_node._emit_exit(FilterBuildingNode.__name__, "Query analysis complete")

    # Test SearchNode exit event
    await search_node._emit_exit(TextResponseNode.__name__, "Search complete")

    # Test TextResponseNode exit event (terminal node)
    await text_response_node._emit_exit(None, "Response generation complete")

    # Verify event sequence
    assert len(emitted_events) == 3
    assert isinstance(emitted_events[0], GraphNodeExitEvent)  # IntentNode exit
    assert isinstance(emitted_events[1], GraphNodeExitEvent)  # SearchNode exit
    assert isinstance(emitted_events[2], GraphNodeExitEvent)  # TextResponseNode exit (terminal)

    # Verify correct node flow and decisions
    assert emitted_events[0].value["node"] == IntentNode.__name__
    assert emitted_events[0].value["next_node"] == FilterBuildingNode.__name__
    assert emitted_events[0].value["decision"] == "Query analysis complete"

    assert emitted_events[1].value["node"] == SearchNode.__name__
    assert emitted_events[1].value["next_node"] == TextResponseNode.__name__
    assert emitted_events[1].value["decision"] == "Search complete"

    assert emitted_events[2].value["node"] == TextResponseNode.__name__
    assert emitted_events[2].value["next_node"] is None  # Terminal node
    assert emitted_events[2].value["decision"] == "Response generation complete"

import pytest

from orchestrator.search.agent.graph_nodes import (
    FilterBuildingNode,
    PlannerNode,
    SearchNode,
    TextResponseNode,
)


@pytest.mark.asyncio
async def test_graph_nodes_creation():
    """Test that graph nodes can be created with event_emitter callback."""
    emitted_events = []

    def event_emitter(event):
        emitted_events.append(event)

    mock_model = "openai:gpt-4"

    # Test node creation with event_emitter
    planner_node = PlannerNode(
        model=mock_model,
        event_emitter=event_emitter,
    )
    search_node = SearchNode(model=mock_model, event_emitter=event_emitter)
    filter_building_node = FilterBuildingNode(model=mock_model, event_emitter=event_emitter)
    text_response_node = TextResponseNode(model=mock_model, event_emitter=event_emitter)

    # Verify nodes were created with correct properties
    assert intent_node.model == mock_model
    assert intent_node.event_emitter == event_emitter
    assert search_node.model == mock_model
    assert search_node.event_emitter == event_emitter
    assert filter_building_node.model == mock_model
    assert filter_building_node.event_emitter == event_emitter
    assert text_response_node.model == mock_model
    assert text_response_node.event_emitter == event_emitter

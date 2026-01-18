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


import pytest
from pydantic_graph import End

from orchestrator.search.agent.agent import GraphAgentAdapter, build_agent_instance
from orchestrator.search.agent.graph_nodes import (
    ExecutionNode,
    FilterBuildingNode,
    QueryAnalysisNode,
    ResponseNode,
    ResultProcessingNode,
)


@pytest.mark.asyncio
async def test_graph_has_all_nodes():
    """Test that graph contains all expected nodes."""
    agent = build_agent_instance("openai:gpt-4o-mini")
    assert isinstance(agent, GraphAgentAdapter)

    nodes = {node_def.node for node_def in agent.graph.node_defs.values()}

    assert nodes == {
        QueryAnalysisNode,
        FilterBuildingNode,
        ExecutionNode,
        ResultProcessingNode,
        ResponseNode,
    }


@pytest.mark.asyncio
async def test_graph_has_correct_edges():
    """Test that graph has correct edges between nodes."""
    agent = build_agent_instance("openai:gpt-4o-mini")
    assert isinstance(agent, GraphAgentAdapter)

    # Build mapping from node_id (string) to node class
    id_to_node = {node_id: node_def.node for node_id, node_def in agent.graph.node_defs.items()}

    # Collect all edges using node classes
    edges = set()
    for node_id, node_def in agent.graph.node_defs.items():
        from_node = id_to_node[node_id]
        # Add transitions to other nodes
        for next_node_id in node_def.next_node_edges:
            to_node = id_to_node[next_node_id]
            edges.add((from_node, to_node))
        # Add end edges
        if node_def.end_edge:
            edges.add((from_node, End))

    assert edges == {
        (QueryAnalysisNode, FilterBuildingNode),
        (FilterBuildingNode, ExecutionNode),
        (ExecutionNode, ResultProcessingNode),
        (ExecutionNode, ResponseNode),
        (ResultProcessingNode, ResponseNode),
        (ResponseNode, End),
    }

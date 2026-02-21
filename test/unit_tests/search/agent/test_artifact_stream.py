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

"""Tests verifying that non-AG-UI consumers (A2A, MCP) see full data from ToolReturn."""

import json

from pydantic_ai.messages import ToolReturnPart

from orchestrator.search.agent.artifacts import DataArtifact, ExportArtifact, QueryArtifact, ToolArtifact
from orchestrator.search.core.types import SearchMetadata
from orchestrator.search.query.results import (
    ExportData,
    QueryResultsResponse,
    ResultRow,
    VisualizationType,
)


def _make_tool_result_with_artifact() -> tuple[QueryResultsResponse, QueryArtifact, ToolReturnPart]:
    """Create a realistic ToolReturnPart as produced by run_search/run_aggregation."""
    full_response = QueryResultsResponse(
        results=[
            ResultRow(
                group_values={"entity_id": "abc-123", "title": "Test Sub", "entity_type": "subscriptions"},
                aggregations={"score": 0.95},
            ),
            ResultRow(
                group_values={"entity_id": "def-456", "title": "Another Sub", "entity_type": "subscriptions"},
                aggregations={"score": 0.82},
            ),
        ],
        total_results=2,
        metadata=SearchMetadata(search_type="hybrid", description="test search"),
        visualization_type=VisualizationType(type="table"),
    )

    artifact = QueryArtifact(
        query_id="q-001",
        total_results=2,
        visualization_type=VisualizationType(type="table"),
        description="Searched 2 subscriptions",
    )

    # This is what pydantic-ai creates from ToolReturn(return_value=full_response, metadata=artifact)
    tool_return_part = ToolReturnPart(
        tool_name="run_search",
        content=full_response,
        tool_call_id="call_123",
        metadata=artifact,
    )

    return full_response, artifact, tool_return_part


def test_a2a_consumer_sees_full_query_results():
    """A2A/MCP consumers access ToolReturnPart.content directly — they get the full QueryResultsResponse.

    There is no AG-UI event stream to replace the content; the LLM and other
    consumers see model_response_str() which serializes the full response.
    """
    full_response, artifact, tool_return_part = _make_tool_result_with_artifact()

    # .content is the full QueryResultsResponse (ToolReturn.return_value)
    a2a_data = tool_return_part.content
    assert isinstance(a2a_data, QueryResultsResponse)
    assert len(a2a_data.results) == 2
    assert a2a_data.results[0].group_values["entity_id"] == "abc-123"
    assert a2a_data.results[1].aggregations["score"] == 0.82
    assert a2a_data.total_results == 2
    assert a2a_data.metadata.search_type == "hybrid"


def test_llm_sees_full_data_via_model_response_str():
    """The LLM receives the full QueryResultsResponse via model_response_str() — not the artifact."""
    _, _, tool_return_part = _make_tool_result_with_artifact()

    llm_content = json.loads(tool_return_part.model_response_str())
    assert "results" in llm_content
    assert len(llm_content["results"]) == 2
    assert llm_content["results"][0]["group_values"]["entity_id"] == "abc-123"
    assert llm_content["total_results"] == 2
    assert llm_content["metadata"]["search_type"] == "hybrid"


def test_artifact_metadata_is_lightweight():
    """The metadata (QueryArtifact) is compact — no result rows, just a reference."""
    _, _, tool_return_part = _make_tool_result_with_artifact()

    assert isinstance(tool_return_part.metadata, QueryArtifact)
    artifact_dict = json.loads(tool_return_part.metadata.model_dump_json())
    assert artifact_dict["query_id"] == "q-001"
    assert artifact_dict["total_results"] == 2
    assert "results" not in artifact_dict


def test_export_artifact_metadata_intercepted():
    """ExportArtifact metadata is recognized as a ToolArtifact by adapters."""
    export_data = ExportData(
        query_id="q-002",
        download_url="http://localhost/api/search/queries/q-002/export",
        message="Export ready for download.",
    )

    artifact = ExportArtifact(
        description="Prepared export for query q-002",
        query_id="q-002",
        download_url="http://localhost/api/search/queries/q-002/export",
    )

    tool_return_part = ToolReturnPart(
        tool_name="prepare_export",
        content=export_data,
        tool_call_id="call_456",
        metadata=artifact,
    )

    # Adapter check: isinstance(metadata, ToolArtifact) catches both QueryArtifact and ExportArtifact
    assert isinstance(tool_return_part.metadata, ToolArtifact)
    assert isinstance(tool_return_part.metadata, ExportArtifact)

    artifact_dict = json.loads(tool_return_part.metadata.model_dump_json())
    assert artifact_dict["query_id"] == "q-002"
    assert artifact_dict["download_url"] == "http://localhost/api/search/queries/q-002/export"
    assert artifact_dict["description"] == "Prepared export for query q-002"

    # Full data is still in .content for non-AG-UI consumers
    assert isinstance(tool_return_part.content, ExportData)
    assert tool_return_part.content.download_url == "http://localhost/api/search/queries/q-002/export"


def test_entity_details_data_artifact_metadata():
    """DataArtifact from fetch_entity_details carries entity info."""
    detailed_json = json.dumps({"subscription_id": "sub-123", "description": "Test"})

    artifact = DataArtifact(
        description="Fetched details for subscriptions sub-123",
        entity_id="sub-123",
        entity_type="subscriptions",
    )

    tool_return_part = ToolReturnPart(
        tool_name="fetch_entity_details",
        content=detailed_json,
        tool_call_id="call_789",
        metadata=artifact,
    )

    assert isinstance(tool_return_part.metadata, ToolArtifact)
    assert isinstance(tool_return_part.metadata, DataArtifact)

    artifact_dict = json.loads(tool_return_part.metadata.model_dump_json())
    assert artifact_dict["entity_id"] == "sub-123"
    assert artifact_dict["entity_type"] == "subscriptions"
    assert "query_id" not in artifact_dict
    assert "download_url" not in artifact_dict


def test_query_artifact_is_tool_artifact():
    """QueryArtifact is also a ToolArtifact — isinstance check works for both."""
    _, artifact, tool_return_part = _make_tool_result_with_artifact()

    assert isinstance(artifact, ToolArtifact)
    assert isinstance(artifact, QueryArtifact)
    assert isinstance(tool_return_part.metadata, ToolArtifact)

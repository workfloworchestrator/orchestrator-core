# Copyright 2019-2026 ESnet.
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

"""Tests for the MCP server integration."""

import json
from contextlib import contextmanager
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp not installed; skipping MCP tests")


@pytest.fixture(scope="module")
def mcp_test_client():
    """TestClient wrapping the MCP ASGI app directly (no auth)."""
    from orchestrator.mcp import create_mcp_app

    app = create_mcp_app(auth_manager=None)
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture(scope="module")
def orchestrator_client_with_mcp(database, db_uri):
    """TestClient for the full OrchestratorCore with MCP mounted.

    Uses TestClient as a context manager so it drives the lifespan (startup/
    shutdown callbacks), which starts and stops the broadcast thread and other
    services. We must NOT manually call broadcast_thread.start() here because
    the on_startup callbacks registered with FastAPI will do it.
    """
    from oauth2_lib.settings import oauth2lib_settings

    from orchestrator.core.app import OrchestratorCore
    from orchestrator.core.settings import app_settings

    with (
        patch.multiple(
            oauth2lib_settings,
            OAUTH2_ACTIVE=False,
            ENVIRONMENT_IGNORE_MUTATION_DISABLED=["local", "TESTING"],
        ),
        patch.multiple(
            app_settings,
            ENVIRONMENT="TESTING",
            # Disable Prometheus to avoid duplicate-registry errors when a
            # second OrchestratorCore is created alongside the session-level one.
            ENABLE_PROMETHEUS_METRICS_ENDPOINT=False,
        ),
        patch("orchestrator.core.settings.llm_settings.MCP_ENABLED", True),
    ):
        app = OrchestratorCore(base_settings=app_settings)
        # TestClient context manager drives on_startup / on_shutdown callbacks.
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

INITIALIZE_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "pytest-harness", "version": "1.0"},
    },
}


def parse_mcp_response(response) -> dict:
    """Parse an MCP response that may be plain JSON or SSE-wrapped JSON."""
    text = response.text
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                pass
    return json.loads(text)


def _mcp_session_headers(client) -> dict:
    """Perform the MCP initialize handshake and return headers with session ID."""
    init_resp = client.post("/", json=INITIALIZE_PAYLOAD, headers=MCP_HEADERS)
    assert init_resp.status_code == HTTPStatus.OK
    headers = {**MCP_HEADERS}
    session_id = init_resp.headers.get("mcp-session-id")
    if session_id:
        headers["mcp-session-id"] = session_id
    return headers


@contextmanager
def _mock_db_scope():
    """Context manager that patches db.database_scope to be a no-op."""
    @contextmanager
    def _noop():
        yield

    with patch("orchestrator.mcp.tools.db.database_scope", _noop):
        yield


def test_mcp_tools_list(mcp_test_client):
    """tools/list should include exactly the 11 orchestrator tool names we registered."""
    headers = _mcp_session_headers(mcp_test_client)

    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    response = mcp_test_client.post("/", json=payload, headers=headers)

    assert response.status_code == HTTPStatus.OK, f"tools/list failed: {response.text[:300]}"

    parsed = parse_mcp_response(response)
    assert "result" in parsed, f"Expected result, got: {parsed}"

    tool_names = [t.get("name") for t in parsed["result"].get("tools", [])]
    expected_tools = [
        "list_workflows",
        "get_workflow_form",
        "create_workflow",
        "resume_workflow_process",
        "abort_workflow_process",
        "get_process_status",
        "list_recent_processes",
        "get_subscription_available_workflows",
        "get_subscription_details",
        "search_subscriptions",
        "list_products",
    ]
    for tool in expected_tools:
        assert tool in tool_names, f"Expected tool '{tool}' not found in {tool_names}"
    assert len(tool_names) == 11, f"Expected exactly 11 tools, got {len(tool_names)}: {tool_names}"


def test_mcp_tools_call_list_workflows(mcp_test_client):
    """tools/call list_workflows should return a valid JSON-RPC result with a JSON array.

    The underlying get_workflows() service is mocked so no database is needed.
    """
    fake_workflow = SimpleNamespace(
        workflow_id="aaaaaaaa-0000-0000-0000-000000000001",
        name="modify_note",
        target="MODIFY",
        is_task=False,
        description="Modify the note on a subscription",
        created_at=None,
        steps=[SimpleNamespace(name="Start"), SimpleNamespace(name="Done")],
    )

    headers = _mcp_session_headers(mcp_test_client)

    with (
        _mock_db_scope(),
        patch("orchestrator.mcp.tools.get_workflows", return_value=[fake_workflow]),
    ):
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "list_workflows", "arguments": {}},
        }
        response = mcp_test_client.post("/", json=payload, headers=headers)

    assert response.status_code == HTTPStatus.OK, f"tools/call failed: {response.text[:300]}"

    parsed = parse_mcp_response(response)
    assert "error" not in parsed, f"Unexpected JSON-RPC error: {parsed.get('error')}"
    assert "result" in parsed, f"Expected result key in: {parsed}"

    # The tool returns a JSON string inside the MCP content array.
    content = parsed["result"].get("content", [])
    assert content, "Expected non-empty content array"
    tool_output = json.loads(content[0]["text"])
    assert isinstance(tool_output, list), f"Expected list of workflows, got: {type(tool_output)}"
    assert len(tool_output) == 1
    assert tool_output[0]["name"] == "modify_note"
    assert tool_output[0]["target"] == "MODIFY"


def test_mcp_tools_call_list_products(mcp_test_client):
    """tools/call list_products should return a valid JSON-RPC result with a JSON array.

    The underlying get_products() service is mocked so no database is needed.
    """
    fake_product = MagicMock()
    fake_product.product_id = "bbbbbbbb-0000-0000-0000-000000000002"
    fake_product.name = "TestProduct"
    fake_product.description = "A test product"
    fake_product.product_type = "TestType"
    fake_product.tag = "TEST"
    fake_product.status = "active"

    headers = _mcp_session_headers(mcp_test_client)

    with (
        _mock_db_scope(),
        patch("orchestrator.mcp.tools.get_products", return_value=[fake_product]),
    ):
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "list_products", "arguments": {}},
        }
        response = mcp_test_client.post("/", json=payload, headers=headers)

    assert response.status_code == HTTPStatus.OK, f"tools/call failed: {response.text[:300]}"

    parsed = parse_mcp_response(response)
    assert "error" not in parsed, f"Unexpected JSON-RPC error: {parsed.get('error')}"
    assert "result" in parsed, f"Expected result key in: {parsed}"

    # The tool returns a JSON string inside the MCP content array.
    content = parsed["result"].get("content", [])
    assert content, "Expected non-empty content array"
    tool_output = json.loads(content[0]["text"])
    assert isinstance(tool_output, list), f"Expected list of products, got: {type(tool_output)}"
    assert len(tool_output) == 1
    assert tool_output[0]["name"] == "TestProduct"
    assert tool_output[0]["product_type"] == "TestType"
    assert tool_output[0]["status"] == "active"


def test_mcp_mounted_at_slash_mcp(orchestrator_client_with_mcp):
    """When MCP_ENABLED=True, /mcp/ should respond to MCP initialize."""
    response = orchestrator_client_with_mcp.post(
        "/mcp/",
        json=INITIALIZE_PAYLOAD,
        headers=MCP_HEADERS,
    )
    assert response.status_code == HTTPStatus.OK, (
        f"Expected 200 at /mcp/, got {response.status_code}: {response.text[:300]}"
    )
    parsed = parse_mcp_response(response)
    result = parsed.get("result", parsed)
    assert "protocolVersion" in result


def test_mcp_not_mounted_when_disabled(database, db_uri):
    """When MCP_ENABLED=False (default), /mcp/ should return 404."""
    from oauth2_lib.settings import oauth2lib_settings

    from orchestrator import OrchestratorCore
    from orchestrator.core.settings import app_settings

    with (
        patch.multiple(
            oauth2lib_settings,
            OAUTH2_ACTIVE=False,
            ENVIRONMENT_IGNORE_MUTATION_DISABLED=["local", "TESTING"],
        ),
        patch.multiple(
            app_settings,
            ENVIRONMENT="TESTING",
            # Disable Prometheus to avoid duplicate-registry errors when a
            # second OrchestratorCore is created alongside the session-level one.
            ENABLE_PROMETHEUS_METRICS_ENDPOINT=False,
        ),
        # MCP_ENABLED defaults to False — no patch needed, but be explicit
        patch("orchestrator.core.settings.llm_settings.MCP_ENABLED", False),
    ):
        app = OrchestratorCore(base_settings=app_settings)
        # TestClient context manager drives on_startup / on_shutdown callbacks.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/mcp/", json=INITIALIZE_PAYLOAD, headers=MCP_HEADERS)
            assert response.status_code == HTTPStatus.NOT_FOUND, (
                f"Expected 404 when MCP disabled, got {response.status_code}"
            )

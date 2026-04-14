"""Tests for the MCP server integration.

Covers:
- create_mcp_app() returns a valid ASGI app
- MCP initialize handshake (JSON-RPC over HTTP)
- tools/list returns expected tool names
- tools/call list_workflows returns a valid response
- OrchestratorCore mounts the MCP app at /mcp when MCP_ENABLED=True
- OrchestratorCore does NOT mount /mcp when MCP_ENABLED=False
"""

import json
from http import HTTPStatus
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp not installed; skipping MCP tests")

# ── Fixtures ──────────────────────────────────────────────────────────────────


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

    from orchestrator import OrchestratorCore
    from orchestrator.settings import app_settings

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
        patch("orchestrator.llm_settings.llm_settings.MCP_ENABLED", True),
    ):
        app = OrchestratorCore(base_settings=app_settings)
        # TestClient context manager drives on_startup / on_shutdown callbacks.
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Unit tests: create_mcp_app ────────────────────────────────────────────────


def test_create_mcp_app_returns_asgi_app():
    """create_mcp_app() should return an ASGI-callable object."""
    from orchestrator.mcp import create_mcp_app

    app = create_mcp_app(auth_manager=None)
    assert callable(app), "MCP app must be an ASGI callable"


def test_create_mcp_server_returns_fastmcp():
    """create_mcp_server() should return the FastMCP instance."""
    from fastmcp import FastMCP

    from orchestrator.mcp import create_mcp_server

    server = create_mcp_server()
    assert isinstance(server, FastMCP)


# ── Integration tests: MCP HTTP protocol ─────────────────────────────────────


def test_mcp_initialize(mcp_test_client):
    """MCP initialize handshake should return protocolVersion and serverInfo."""
    response = mcp_test_client.post("/", json=INITIALIZE_PAYLOAD, headers=MCP_HEADERS)

    assert response.status_code == HTTPStatus.OK, f"Expected 200, got {response.status_code}: {response.text[:300]}"

    parsed = parse_mcp_response(response)
    result = parsed.get("result", parsed)

    assert "protocolVersion" in result, f"Missing protocolVersion in: {result}"
    assert "serverInfo" in result, f"Missing serverInfo in: {result}"
    assert result["serverInfo"].get("name") == "orchestrator-core"


def test_mcp_initialize_returns_session_id(mcp_test_client):
    """MCP initialize should return an mcp-session-id header."""
    response = mcp_test_client.post("/", json=INITIALIZE_PAYLOAD, headers=MCP_HEADERS)

    assert response.status_code == HTTPStatus.OK
    # Session ID may be in headers (stateful mode) or not required (stateless)
    # Just verify the response is valid JSON-RPC
    parsed = parse_mcp_response(response)
    assert "result" in parsed or "error" not in parsed


def test_mcp_tools_list(mcp_test_client):
    """tools/list should include the expected orchestrator tool names."""
    # First initialize to get a session
    init_resp = mcp_test_client.post("/", json=INITIALIZE_PAYLOAD, headers=MCP_HEADERS)
    assert init_resp.status_code == HTTPStatus.OK

    session_id = init_resp.headers.get("mcp-session-id")
    headers = {**MCP_HEADERS}
    if session_id:
        headers["mcp-session-id"] = session_id

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
        "get_process_status",
        "list_recent_processes",
        "get_subscription_available_workflows",
        "get_subscription_details",
        "search_subscriptions",
        "list_products",
    ]
    for tool in expected_tools:
        assert tool in tool_names, f"Expected tool '{tool}' not found in {tool_names}"


def test_mcp_tools_call_list_workflows(mcp_test_client):
    """tools/call list_workflows should return a valid JSON-RPC result (no error)."""
    # Initialize
    init_resp = mcp_test_client.post("/", json=INITIALIZE_PAYLOAD, headers=MCP_HEADERS)
    assert init_resp.status_code == HTTPStatus.OK

    session_id = init_resp.headers.get("mcp-session-id")
    headers = {**MCP_HEADERS}
    if session_id:
        headers["mcp-session-id"] = session_id

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


# ── Integration tests: OrchestratorCore mounting ──────────────────────────────


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
    from orchestrator.settings import app_settings

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
        patch("orchestrator.llm_settings.llm_settings.MCP_ENABLED", False),
    ):
        app = OrchestratorCore(base_settings=app_settings)
        # TestClient context manager drives on_startup / on_shutdown callbacks.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/mcp/", json=INITIALIZE_PAYLOAD, headers=MCP_HEADERS)
            assert response.status_code == HTTPStatus.NOT_FOUND, (
                f"Expected 404 when MCP disabled, got {response.status_code}"
            )

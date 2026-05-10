# Copyright 2019-2026 SURF, GÉANT.
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

"""Tests for the MCP (Model Context Protocol) server integration.

These tests verify that:

1. The agent-tagged REST routes carry ``AgentTag.EXPOSED`` and have
   stable ``operation_id`` values that map 1:1 to the MCP tool names.
2. ``FastMCP.from_fastapi`` introspects the FastAPI app's routes, derives
   input schemas from their pydantic models, and produces exactly the 11
   tools we expect via ``RouteMap`` tag-based filtering.

"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from orchestrator.core.agent_tags import AgentTag
from orchestrator.core.api.api_v1.endpoints import mcp_tools, processes, products

# All tool names must match the ``operation_id`` on each tagged route.
EXPECTED_TOOL_NAMES = {
    "create_workflow",  # POST /api/processes/{workflow_key}
    "resume_workflow_process",  # PUT /api/processes/{process_id}/resume
    "abort_workflow_process",  # PUT /api/processes/{process_id}/abort
    "list_products",  # GET /api/products/
    "list_workflows",
    "get_workflow_form",
    "get_subscription_available_workflows",
    "get_process_status",
    "list_recent_processes",
    "get_subscription_details",
    "search_subscriptions",
}


def _agent_tagged_routes(app: FastAPI) -> dict[str, str]:
    """Return ``{operation_id: path}`` for every route tagged ``AgentTag.EXPOSED``.

    Iterates the merged FastAPI route table (covers both APIRouter-included
    routes and routes added via ``@app.router.get`` etc.).
    """
    out: dict[str, str] = {}
    for route in app.routes:
        tags = getattr(route, "tags", None) or []
        if AgentTag.EXPOSED.value in tags or AgentTag.EXPOSED in tags:
            op_id = getattr(route, "operation_id", None)
            path = getattr(route, "path", "")
            assert op_id, f"agent-exposed route {path!r} is missing operation_id"
            out[op_id] = path
    return out


@pytest.fixture
def app_with_agent_routes() -> FastAPI:
    """A bare FastAPI app with just the agent-relevant routers mounted.

    Overrides the ``authenticate`` / ``authorize`` deps to no-ops because the
    real implementations dereference ``request.app.auth_manager`` which only
    ``OrchestratorCore`` sets up. The MCP path through ``tools/list`` doesn't
    actually invoke any tool body, so swapping these out is safe for the
    listing test.
    """
    from orchestrator.core.security import authenticate, authorize

    app = FastAPI(title="orchestrator-core-mcp-test", version="test")
    app.include_router(processes.router, prefix="/api/processes")
    app.include_router(products.router, prefix="/api/products")
    app.include_router(mcp_tools.router, prefix="/api/agent")
    app.dependency_overrides[authenticate] = lambda: None
    app.dependency_overrides[authorize] = lambda: None
    return app


def test_all_expected_routes_carry_agent_tag(app_with_agent_routes: FastAPI) -> None:
    """Every expected MCP tool name has a route tagged ``AgentTag.EXPOSED``."""
    found = _agent_tagged_routes(app_with_agent_routes)
    assert (
        set(found) == EXPECTED_TOOL_NAMES
    ), f"missing: {EXPECTED_TOOL_NAMES - set(found)}, extra: {set(found) - EXPECTED_TOOL_NAMES}"


@pytest.mark.asyncio
async def test_fastmcp_introspects_all_expected_tools(app_with_agent_routes: FastAPI) -> None:
    """``FastMCP.from_fastapi`` produces exactly the expected tools from the tagged routes.

    Filtering uses ``RouteMap`` precedence: routes carrying ``AgentTag.EXPOSED``
    map to ``MCPType.TOOL``, everything else falls through to ``EXCLUDE``.

    Each tool's ``parameters`` is also asserted to contain a ``properties``
    object, this verifies that fastmcp successfully derived a JSON schema
    from each route's pydantic models and path/query parameters.
    """
    pytest.importorskip("fastmcp")
    from fastmcp import FastMCP
    from fastmcp.server.providers.openapi import MCPType, RouteMap

    mcp = FastMCP.from_fastapi(
        app=app_with_agent_routes,
        name="orchestrator-core-mcp-test",
        route_maps=[
            RouteMap(tags={AgentTag.EXPOSED.value}, mcp_type=MCPType.TOOL),
            RouteMap(mcp_type=MCPType.EXCLUDE),
        ],
    )

    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}
    assert (
        tool_names == EXPECTED_TOOL_NAMES
    ), f"missing: {EXPECTED_TOOL_NAMES - tool_names}, extra: {tool_names - EXPECTED_TOOL_NAMES}"

    for tool in tools:
        assert isinstance(tool.parameters, dict), f"tool {tool.name} has non-dict parameters"
        assert "properties" in tool.parameters, f"tool {tool.name} parameters missing 'properties'"

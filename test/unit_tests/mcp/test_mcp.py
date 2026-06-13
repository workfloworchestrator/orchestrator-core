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
   input schemas from their pydantic models, and produces exactly the 22
   tools we expect via ``RouteMap`` tag-based filtering.
3. Each tool carries ``ToolAnnotations`` (read-only/idempotent/destructive
   hints + a humanized title) derived from its HTTP method and ``AgentTag``s.

"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

from orchestrator.core.agent_tags import AgentTag
from orchestrator.core.api.api_v1.endpoints import (
    mcp_tools,
    processes,
    product_blocks,
    products,
    resource_types,
    subscriptions,
    workflows,
)
from orchestrator.core.exception_handlers import query_validation_handler
from orchestrator.core.search.query.exceptions import InvalidLtreePatternError, PathNotFoundError, QueryValidationError

if TYPE_CHECKING:
    from fastmcp.tools.tool import Tool

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
    "get_product",  # GET /api/products/{product_id}
    "get_product_block",  # GET /api/product_blocks/{product_block_id}
    "get_resource_type",  # GET /api/resource_types/{resource_type_id}
    "get_workflow_by_id",  # GET /api/workflows/{workflow_id}
    "get_subscription_domain_model",  # GET /api/subscriptions/domain-model/{subscription_id}
    "get_process_status_counts",  # GET /api/processes/status-counts
    "search",  # POST /api/agent/search
    "aggregate",  # POST /api/agent/aggregate
    "discover_filter_paths",  # POST /api/agent/discover_filter_paths
    "get_valid_operators",  # POST /api/agent/get_valid_operators
    "resolve_entity",  # POST /api/agent/resolve_entity
    "export_query",  # POST /api/agent/export_query
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
    app.include_router(workflows.router, prefix="/api/workflows")
    app.include_router(product_blocks.router, prefix="/api/product_blocks")
    app.include_router(resource_types.router, prefix="/api/resource_types")
    app.include_router(subscriptions.router, prefix="/api/subscriptions")
    app.dependency_overrides[authenticate] = lambda: None
    app.dependency_overrides[authorize] = lambda: None
    # Mirror OrchestratorCore.__init__: search-layer validation errors -> 422.
    app.add_exception_handler(QueryValidationError, query_validation_handler)  # type: ignore[arg-type]
    return app


def test_all_expected_routes_carry_agent_tag(app_with_agent_routes: FastAPI) -> None:
    """Every expected MCP tool name has a route tagged ``AgentTag.EXPOSED``."""
    found = _agent_tagged_routes(app_with_agent_routes)
    assert set(found) == EXPECTED_TOOL_NAMES, (
        f"missing: {EXPECTED_TOOL_NAMES - set(found)}, extra: {set(found) - EXPECTED_TOOL_NAMES}"
    )


@pytest.mark.asyncio
async def test_fastmcp_introspects_all_expected_tools(app_with_agent_routes: FastAPI) -> None:
    """``build_mcp`` produces exactly the expected tools from the tagged routes."""
    pytest.importorskip("fastmcp")
    from orchestrator.core.mcp.server import build_mcp

    mcp = build_mcp(app_with_agent_routes)

    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}
    assert tool_names == EXPECTED_TOOL_NAMES, (
        f"missing: {EXPECTED_TOOL_NAMES - tool_names}, extra: {tool_names - EXPECTED_TOOL_NAMES}"
    )

    for tool in tools:
        assert isinstance(tool.parameters, dict), f"tool {tool.name} has non-dict parameters"
        assert "properties" in tool.parameters, f"tool {tool.name} parameters missing 'properties'"


async def _tools_by_name(app: FastAPI) -> dict[str, Tool]:
    from orchestrator.core.mcp.server import build_mcp

    mcp = build_mcp(app)
    return {tool.name: tool for tool in await mcp.list_tools()}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name, read_only, idempotent, destructive",
    [
        pytest.param("get_process_status", True, True, False, id="readonly-post"),
        pytest.param("list_products", True, True, False, id="readonly-get"),
        pytest.param("create_workflow", False, False, False, id="write-post"),
        pytest.param("resume_workflow_process", False, True, False, id="idempotent-put"),
        pytest.param("abort_workflow_process", False, True, True, id="destructive-put"),
        pytest.param("get_product", True, True, False, id="readonly-get-by-id"),
        pytest.param("get_product_block", True, True, False, id="readonly-product-block"),
        pytest.param("get_resource_type", True, True, False, id="readonly-resource-type"),
        pytest.param("get_workflow_by_id", True, True, False, id="readonly-workflow"),
        pytest.param("get_subscription_domain_model", True, True, False, id="readonly-domain-model"),
        pytest.param("get_process_status_counts", True, True, False, id="readonly-status-counts"),
        pytest.param("search", True, True, False, id="readonly-search"),
        pytest.param("aggregate", True, True, False, id="readonly-aggregate"),
        pytest.param("discover_filter_paths", True, True, False, id="readonly-discover-filter-paths"),
        pytest.param("get_valid_operators", True, True, False, id="readonly-get-valid-operators"),
        pytest.param("resolve_entity", True, True, False, id="readonly-resolve-entity"),
        pytest.param("export_query", True, True, False, id="readonly-export-query"),
    ],
)
async def test_tool_annotations(
    app_with_agent_routes: FastAPI,
    tool_name: str,
    read_only: bool,
    idempotent: bool,
    destructive: bool,
) -> None:
    """Each tool's ToolAnnotations reflect its method + AgentTag signals."""
    pytest.importorskip("fastmcp")
    tool = (await _tools_by_name(app_with_agent_routes))[tool_name]
    ann = tool.annotations
    assert ann is not None
    assert ann.readOnlyHint is read_only
    assert ann.idempotentHint is idempotent
    assert ann.destructiveHint is destructive
    assert ann.openWorldHint is False


@pytest.mark.asyncio
async def test_all_tools_have_title_and_closed_world(app_with_agent_routes: FastAPI) -> None:
    """Every tool gets a non-empty humanized title and openWorldHint=False."""
    pytest.importorskip("fastmcp")
    for name, tool in (await _tools_by_name(app_with_agent_routes)).items():
        assert tool.annotations is not None, name
        assert tool.annotations.title, name
        assert tool.annotations.openWorldHint is False, name


def test_exposed_routes_have_docstrings(app_with_agent_routes: FastAPI) -> None:
    """Every agent-exposed route has a non-empty docstring (its MCP tool description)."""
    missing = [
        getattr(route, "path", "")
        for route in app_with_agent_routes.routes
        if (AgentTag.EXPOSED.value in (getattr(route, "tags", None) or []))
        and not ((getattr(getattr(route, "endpoint", None), "__doc__", "") or "").strip())
    ]
    assert not missing, f"agent-exposed routes missing a docstring: {missing}"


_BOGUS_FILTER = {
    "op": "AND",
    "children": [{"path": "subscription.bogus", "condition": {"op": "eq", "value": "x"}, "value_kind": "string"}],
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc, expected_detail",
    [
        pytest.param(
            PathNotFoundError("subscription.bogus"),
            "Path 'subscription.bogus' does not exist in the database. Use discover_filter_paths to find valid paths.",
            id="path-not-found-appends-hint",
        ),
        pytest.param(
            InvalidLtreePatternError("sub.*.["),
            "Ltree pattern 'sub.*.[' has invalid syntax. Use valid PostgreSQL ltree lquery syntax.",
            id="other-validation-error-plain-message",
        ),
    ],
)
async def test_query_validation_error_surfaces_as_422_through_mcp(
    app_with_agent_routes: FastAPI, exc: QueryValidationError, expected_detail: str
) -> None:
    """A QueryValidationError raised in an endpoint reaches the MCP caller as a 422 with its message.

    fastmcp invokes routes via in-process httpx over ASGITransport, so the app's exception handler
    fires and the LLM gets the helpful detail instead of an opaque 500. Guards that wiring.
    """
    pytest.importorskip("fastmcp")
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    from orchestrator.core.mcp.server import build_mcp

    with patch.object(mcp_tools, "validate_filter_tree", AsyncMock(side_effect=exc)):
        mcp = build_mcp(app_with_agent_routes)
        async with Client(mcp) as client:
            with pytest.raises(ToolError) as excinfo:
                await client.call_tool("search", {"entity_type": "SUBSCRIPTION", "filters": _BOGUS_FILTER})

    message = str(excinfo.value)
    assert "422" in message
    assert expected_detail in message

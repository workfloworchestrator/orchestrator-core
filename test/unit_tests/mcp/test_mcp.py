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

1. The agent-tagged REST routes carry the ``AGENT_EXPOSED_TAG`` and have
   stable ``operation_id`` values that map 1:1 to the MCP tool names.
2. ``FastMCP.from_fastapi`` introspects the FastAPI app's routes, derives
   input schemas from their pydantic models, and produces exactly the 23
   tools we expect via ``RouteMap`` tag-based filtering.
3. Each tool carries ``ToolAnnotations`` (read-only/idempotent/destructive
   hints + a humanized title) declared per route via ``openapi_extra``
   (``x-mcp-annotations``).

"""

from __future__ import annotations

import json
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING, Annotated
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ConfigDict, Field

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
from orchestrator.core.forms import FormPage
from orchestrator.core.forms.validators import Choice, Label
from orchestrator.core.mcp.server import AGENT_EXPOSED_TAG
from orchestrator.core.schemas.mcp_tools import GetWorkflowFormRequest, WorkflowFormPage
from orchestrator.core.search.query.exceptions import InvalidLtreePatternError, PathNotFoundError, QueryValidationError
from pydantic_forms.core import page_schema
from pydantic_forms.exception_handlers.fastapi import form_error_handler
from pydantic_forms.exceptions import FormException

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
    "get_workflow_form_options",
    "get_subscription_available_workflows",
    "get_process_status",
    "list_recent_processes",
    "list_subscriptions",
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


# OpenAPI path-item keys that describe an actual operation (vs. ``parameters`` etc.).
_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _exposed_operations(app: FastAPI) -> list[tuple[str, str, dict]]:
    """Yield ``(path, method, operation)`` for every operation tagged ``AGENT_EXPOSED_TAG``.

    Reads the generated OpenAPI spec rather than walking ``app.routes`` directly.
    As of FastAPI 0.138 ``include_router`` mounts routes lazily behind an internal
    ``_IncludedRouter`` wrapper, so ``app.routes`` no longer yields the flattened
    ``APIRoute`` objects. The agent tag lands unchanged in the OpenAPI spec, which
    is the stable, public contract that downstream consumers — including
    ``FastMCP.from_fastapi`` — actually read.
    """
    return [
        (path, method, operation)
        for path, methods in app.openapi()["paths"].items()
        for method, operation in methods.items()
        if method in _HTTP_METHODS and AGENT_EXPOSED_TAG in (operation.get("tags") or [])
    ]


def _agent_tagged_routes(app: FastAPI) -> dict[str, str]:
    """Return ``{operation_id: path}`` for every operation tagged ``AGENT_EXPOSED_TAG``."""
    out: dict[str, str] = {}
    for path, _method, operation in _exposed_operations(app):
        op_id = operation.get("operationId")
        assert op_id, f"agent-exposed route {path!r} is missing operationId"
        out[op_id] = path
    return out


@pytest.fixture
def app_with_agent_routes() -> FastAPI:
    """A bare FastAPI app with just the agent-relevant routers mounted.

    Overrides the ``authenticate`` / ``authorize`` deps to no-ops because the
    real implementations dereference ``request.app.auth_manager`` which only
    ``OrchestratorCore`` sets up. The MCP path through ``tools/list`` doesn't
    actually invoke any tool body, so swapping these out is safe for the
    listing test. ``get_async_session`` is also overridden with a bare
    ``AsyncMock`` since no real database is configured for this app.
    """
    from orchestrator.core.db import get_async_session
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
    app.dependency_overrides[get_async_session] = lambda: AsyncMock()
    # Mirror OrchestratorCore.__init__: search-layer validation errors -> 422, a rejected form page -> 400.
    app.add_exception_handler(QueryValidationError, query_validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(FormException, form_error_handler)  # type: ignore[arg-type]
    return app


def test_all_expected_routes_carry_agent_tag(app_with_agent_routes: FastAPI) -> None:
    """Every expected MCP tool name has a route tagged ``AGENT_EXPOSED_TAG``."""
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
    """Each tool's ToolAnnotations reflect the hints declared on its route."""
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
    """Every agent-exposed route has a non-empty docstring (its MCP tool description).

    FastAPI surfaces the endpoint docstring as the OpenAPI operation
    ``description``, which is what ``FastMCP.from_fastapi`` turns into the tool
    description.
    """
    missing = [
        path
        for path, _method, operation in _exposed_operations(app_with_agent_routes)
        if not (operation.get("description") or "").strip()
    ]
    assert missing == [], f"agent-exposed routes missing a docstring: {missing}"


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


def test_search_without_criteria_rejected_as_422(app_with_agent_routes: FastAPI) -> None:
    """A search call with neither ``query_text`` nor ``filters`` fails loudly.

    Guards the ``SearchToolRequest`` validator: a criteria-less search used to
    rank nothing and return an empty result set, which LLM callers reported as
    "no data" instead of recognizing a bad call. (That a 422 reaches the MCP
    caller as a ToolError is covered by
    ``test_query_validation_error_surfaces_as_422_through_mcp``.)
    """
    client = TestClient(app_with_agent_routes)
    response = client.post("/api/agent/search", json={"entity_type": "SUBSCRIPTION"})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- the form tool: a page as one JSON Schema, a verdict as a result -------------------------------------


class _Speed(Choice):
    ten = ("10G", "10 Gbit/s")


class _PortPage(FormPage):
    model_config = ConfigDict(title="Port")

    note: Label
    speed: _Speed
    vlan: int = 0


def _port_form(state):
    yield _PortPage
    return state


_PORT_WORKFLOW = SimpleNamespace(initial_input_form=_port_form, target="CREATE")


async def _form_tool(app: FastAPI, arguments: dict) -> dict:
    """Call ``get_workflow_form`` for the port workflow through fastmcp; the structured result."""
    from fastmcp import Client

    from orchestrator.core.mcp.server import build_mcp

    with patch.object(mcp_tools, "get_workflow", return_value=_PORT_WORKFLOW):
        async with Client(build_mcp(app)) as client:
            result = await client.call_tool("get_workflow_form", {"workflow_key": "create_port", **arguments})
    assert result.structured_content is not None
    return result.structured_content


@pytest.mark.asyncio
async def test_get_workflow_form_serves_the_page_as_one_schema(app_with_agent_routes: FastAPI, monkeypatch) -> None:
    pytest.importorskip("fastmcp")
    labels = {"note": "Notes", "note_info": "Reminders", "vlan_info": "The vlan id"}
    monkeypatch.setattr(mcp_tools, "form_field_labels", lambda language: labels if language == "en-GB" else {})
    first = await _form_tool(app_with_agent_routes, {})
    assert (first["status"], first["page"], first["complete"], first["title"]) == ("next", 0, False, "Port")
    schema = first["schema"]
    plain = page_schema(_PortPage, inline_refs=True)
    assert schema["properties"]["speed"] == plain["properties"]["speed"]  # no label: as pydantic-forms renders it
    assert (schema["properties"]["note"]["title"], schema["properties"]["note"]["description"]) == (
        "Notes",
        "Reminders",
    )
    assert (
        schema["properties"]["vlan"]["description"] == "The vlan id"
    )  # the form translations, as the frontend shows them
    assert {k: v for k, v in schema.items() if k != "properties"} == {
        k: v for k, v in plain.items() if k != "properties"
    }
    other = await _form_tool(app_with_agent_routes, {"language": "nl-NL"})  # a language without a table
    assert other["schema"] == plain
    assert "$defs" not in schema and "$ref" not in json.dumps(schema)  # the choice is inlined
    assert list(schema["properties"]) == ["note", "speed", "vlan"] and schema["required"] == ["speed"]
    assert schema["properties"]["note"]["readOnly"] is True  # a label: shown, nothing to submit
    speed = schema["properties"]["speed"]
    assert (speed["enum"], speed["options"]) == (["10G"], {"10G": "10 Gbit/s"})
    assert "fields" not in first and WorkflowFormPage.model_fields["schema_"].deprecated is None
    assert "include_schema" not in GetWorkflowFormRequest.model_fields
    done = await _form_tool(app_with_agent_routes, {"page_inputs": [{"speed": "10G"}]})
    assert (done["status"], done["page"], done["complete"], done["schema"]) == ("complete", 1, True, None)


@pytest.mark.asyncio
async def test_a_rejected_page_is_an_error_or_a_result_as_asked(app_with_agent_routes: FastAPI) -> None:
    pytest.importorskip("fastmcp")
    from fastmcp.exceptions import ToolError

    bad = {"page_inputs": [{"speed": "100G"}]}
    with pytest.raises(ToolError) as excinfo:  # the default, as before: a 400 carrying the form's error body
        await _form_tool(app_with_agent_routes, bad)
    assert "400" in str(excinfo.value) and "speed" in str(excinfo.value)
    rejected = await _form_tool(app_with_agent_routes, {**bad, "verdict": "result"})
    assert (rejected["status"], rejected["page"], rejected["complete"]) == ("rejected", 0, False)
    assert [(e["loc"], e["type"]) for e in rejected["errors"]] == [(["speed"], "enum")]
    first = await _form_tool(app_with_agent_routes, {})
    assert rejected["schema"] == first["schema"]  # the page to resubmit, labelled as it was served


# --- sourced fields: a short list in the schema, a long one through the options tool ----------------------

_CUSTOMERS = [{"id": f"c-{n:02d}", "name": f"Customer {n:02d}"} for n in range(30)]
_NODES = {"ams": ["ams-1", "ams-2"], "utr": ["utr-1"]}
_PORTS = [{"id": f"p-{n:03d}", "name": f"Port {n:03d}"} for n in range(100)]


def _first_ports(q: str = "", by: tuple[str, ...] = ("id", "name")) -> list[dict]:
    """A route that searches on the server: three rows at a time, of those ``q`` fits."""
    return [port for port in _PORTS if any(q in port[key] for key in by)][:3]


def _one_port(port: str) -> dict:
    if (found := next((row for row in _PORTS if row["id"] == port), None)) is None:
        raise HTTPException(status_code=404)
    return found


def _source(url: str, **more: str | dict) -> dict:
    return {"json_schema_extra": {"optionsSource": {"url": url, **more}}}


class _SourcedPage(FormPage):
    customer: Annotated[str, Field(**_source("/options/customers", value="id", label="name"))]
    location: Annotated[str, Field(**_source("/options/locations"))]
    node: Annotated[str | None, Field(**_source("/options/nodes/{code}", dependsOn={"code": "1/location"}))] = None
    broken: Annotated[str | None, Field(**_source("/options/missing"))] = None
    port: Annotated[
        str | None,
        Field(**_source("/options/ports", search="q", lookup="/options/ports/{value}", value="id", label="name")),
    ] = None
    uplink: Annotated[str | None, Field(**_source("/options/uplinks", search="q", value="id", label="name"))] = None


def _sourced_form(state):
    yield _SourcedPage
    return state


_SOURCED_WORKFLOW = SimpleNamespace(initial_input_form=_sourced_form, target="CREATE")


@pytest.fixture
def app_with_options(app_with_agent_routes: FastAPI) -> FastAPI:
    """The app with the routes the sourced page's fields point at."""
    app_with_agent_routes.add_api_route("/options/customers", lambda: _CUSTOMERS)
    app_with_agent_routes.add_api_route("/options/locations", lambda: list(_NODES))
    app_with_agent_routes.add_api_route("/options/nodes/{code}", lambda code: _NODES[code])
    app_with_agent_routes.add_api_route("/options/ports", lambda q="": _first_ports(q))
    app_with_agent_routes.add_api_route("/options/ports/{port}", _one_port)
    app_with_agent_routes.add_api_route("/options/uplinks", lambda q="": _first_ports(q, by=("name",)))
    return app_with_agent_routes


async def _sourced_tool(app: FastAPI, tool: str, arguments: dict) -> dict:
    from fastmcp import Client

    from orchestrator.core.mcp.server import build_mcp

    with patch.object(mcp_tools, "get_workflow", return_value=_SOURCED_WORKFLOW):
        async with Client(build_mcp(app)) as client:
            result = await client.call_tool(tool, {"workflow_key": "create_sourced", **arguments})
    assert result.structured_content is not None
    return result.structured_content


@pytest.mark.asyncio
async def test_a_short_sourced_list_is_written_into_the_schema_and_a_long_one_is_left_to_the_tool(
    app_with_options: FastAPI,
) -> None:
    pytest.importorskip("fastmcp")
    properties = (await _sourced_tool(app_with_options, "get_workflow_form", {}))["schema"]["properties"]
    assert properties["location"]["enum"] == ["ams", "utr"] and "optionsSource" not in properties["location"]
    assert properties["location"]["options"] == {"ams": "ams", "utr": "utr"}
    # too long, waiting for the location, unreadable, and searched on the server: each keeps its source
    kept = ("customer", "node", "broken", "port", "uplink")
    assert all("optionsSource" in json.dumps(properties[name]) for name in kept)
    assert "enum" not in json.dumps(properties["port"])  # its three rows without a term are not the list
    assert "enum" not in json.dumps(properties["customer"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments,values,total",
    [
        ({"field": "customer", "search": "customer 07"}, [f"c-{n:02d}" for n in range(30)], 30),  # fits: whole
        ({"field": "customer", "search": "c-1", "limit": 5}, [f"c-{n}" for n in range(10, 15)], 10),
        ({"field": "customer", "limit": 2}, ["c-00", "c-01"], 30),
        ({"field": "node", "page_values": {"location": "ams"}}, ["ams-1", "ams-2"], 2),
    ],
)
async def test_the_options_tool_finds_a_sourced_fields_options(
    app_with_options: FastAPI, arguments: dict, values: list[str], total: int
) -> None:
    pytest.importorskip("fastmcp")
    found = await _sourced_tool(app_with_options, "get_workflow_form_options", arguments)
    assert ([option["value"] for option in found["options"]], found["total"]) == (values, total)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments,status,said",
    [
        ({"field": "node"}, "400", "depend on code"),
        ({"field": "nothing"}, "400", "no options source"),
        ({"field": "broken"}, "502", "could not be read"),
        ({"field": "node", "page_values": {"location": ".."}}, "502", "would change the path"),
        ({"field": "customer", "page_inputs": [{"customer": "c-01", "location": "ams"}]}, "400", "page_inputs"),
    ],
)
async def test_the_options_tool_says_why_it_has_no_options(
    app_with_options: FastAPI, arguments: dict, status: str, said: str
) -> None:
    pytest.importorskip("fastmcp")
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError) as excinfo:
        await _sourced_tool(app_with_options, "get_workflow_form_options", arguments)
    assert status in str(excinfo.value) and said in str(excinfo.value)


@pytest.mark.asyncio
async def test_a_sourced_value_nobody_was_offered_is_rejected_and_an_offered_one_is_labelled(
    app_with_options: FastAPI,
) -> None:
    pytest.importorskip("fastmcp")
    from fastmcp.exceptions import ToolError

    invented = {"page_inputs": [{"customer": "Customer 07", "location": "ams", "node": "utr-1"}]}
    rejected = await _sourced_tool(app_with_options, "get_workflow_form", {**invented, "verdict": "result"})
    assert (rejected["status"], rejected["page"]) == ("rejected", 0)
    assert [error["loc"] for error in rejected["errors"]] == [["customer"], ["node"]]
    assert rejected["schema"]["properties"]["node"]["enum"] == ["ams-1", "ams-2"]  # the location is known now
    with pytest.raises(ToolError) as excinfo:
        await _sourced_tool(app_with_options, "get_workflow_form", invented)
    assert "400" in str(excinfo.value) and "customer" in str(excinfo.value)
    offered = {"page_inputs": [{"customer": "c-07", "location": "ams", "node": "ams-2", "broken": "anything"}]}
    done = await _sourced_tool(app_with_options, "get_workflow_form", offered)
    assert done["status"] == "complete"
    assert done["labels"] == {"customer": "Customer 07", "location": "ams", "node": "ams-2"}  # unreadable: not judged


@pytest.mark.asyncio
async def test_a_searching_source_is_judged_through_its_lookup_and_not_at_all_without_one(
    app_with_options: FastAPI,
) -> None:
    pytest.importorskip("fastmcp")
    found = await _sourced_tool(app_with_options, "get_workflow_form_options", {"field": "port", "search": "077"})
    assert [option["value"] for option in found["options"]] == ["p-077"]
    page = {"customer": "c-07", "location": "ams", "port": "p-077", "uplink": "p-077"}
    done = await _sourced_tool(app_with_options, "get_workflow_form", {"page_inputs": [page]})
    # Neither route lists p-077 without a term. The port has a lookup, so it is checked and labelled; the
    # uplink has none, so it is accepted as it came.
    assert done["status"] == "complete"
    assert done["labels"] == {"customer": "Customer 07", "location": "ams", "port": "Port 077"}
    invented = {"page_inputs": [{**page, "port": "p-999", "uplink": "p-999"}], "verdict": "result"}
    rejected = await _sourced_tool(app_with_options, "get_workflow_form", invented)
    assert [error["loc"] for error in rejected["errors"]] == [["port"]]


@pytest.mark.asyncio
async def test_list_workflows_takes_a_call_without_arguments(app_with_agent_routes: FastAPI) -> None:
    pytest.importorskip("fastmcp")
    from fastmcp import Client

    from orchestrator.core.mcp.server import build_mcp

    listed = AsyncMock(return_value=[])
    with patch.object(mcp_tools, "get_workflows_async", listed):
        async with Client(build_mcp(app_with_agent_routes)) as client:
            await client.call_tool("list_workflows", {})
    listed.assert_awaited_once()
    assert listed.await_args is not None and listed.await_args.kwargs["filters"] is None

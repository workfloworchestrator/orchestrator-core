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

"""MCP (Model Context Protocol) server exposing orchestrator-core operations as tools.

Mounted into ``OrchestratorCore`` at ``/mcp`` when ``MCP_ENABLED=True`` (see
``orchestrator/core/app.py``).

Tools are **auto-generated from the FastAPI app's routes** via ``fastmcp``'s
``FastMCP.from_fastapi(app=...)``. Every REST operation tagged
``AGENT_EXPOSED_TAG`` becomes an MCP tool with a typed parameter schema
derived from the route's pydantic models, plus the route's docstring as the
tool description.

Behavioral metadata (``readOnlyHint``, ``destructiveHint``, ``idempotentHint``,
``openWorldHint``) is declared per route via ``openapi_extra`` under the
``x-mcp-annotations`` key. Routes pick one of the prebuilt ``*_TOOL`` openapi-extra
constants below; ``_build_component_fn`` reads them and stamps each generated tool's
``mcp.types.ToolAnnotations`` (defaulting ``title`` to a humanized operation_id).
The hints are plain dicts (not ``ToolAnnotations`` objects) so route modules never
import ``mcp``/``fastmcp`` — those stay an optional extra, imported lazily here.

Auth: ``from_fastapi`` invokes routes via in-process ``httpx`` over
``ASGITransport``, which goes through the FastAPI middleware + dependency
chain so the existing ``Depends(authorize)`` on each route fires normally
when the LLM calls the corresponding MCP tool. We just need to
forward the incoming MCP request's ``Authorization`` header into that
inner httpx call, which fastmcp does NOT do by default, its
``get_http_headers()`` default exclude list strips ``authorization``.
The ``_forward_auth_header`` httpx request hook below
re-injects it. See https://github.com/jlowin/fastmcp/issues/2817.

Transport: streamable HTTP.
"""

from itertools import chain
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import FastAPI
from starlette.applications import Starlette

if TYPE_CHECKING:
    from fastmcp import FastMCP

MCP_MOUNT_PATH = "/mcp"

# FastAPI tag that gates MCP exposure: tag a route with this to surface it as an
# MCP tool. Routes without it are excluded. Routes import this from here.
AGENT_EXPOSED_TAG = "agent-exposed"

# openapi_extra key carrying a route's MCP ToolAnnotations hints.
MCP_ANNOTATIONS_EXTENSION = "x-mcp-annotations"

# Prebuilt ``openapi_extra`` values a route can pass verbatim (kept as plain dicts so
# route modules don't import the optional ``mcp`` package). One per behavioral shape:
#   READONLY_TOOL         GET getters + curated POST read-tools (no state change)
#   WRITE_TOOL            non-idempotent mutation (e.g. create_workflow)
#   IDEMPOTENT_WRITE_TOOL idempotent mutation (e.g. resume_workflow_process — a PUT)
#   DESTRUCTIVE_TOOL      irreversible mutation (e.g. abort_workflow_process)
# ``openWorldHint`` is always False — the orchestrator acts on its own database.
READONLY_TOOL = {
    MCP_ANNOTATIONS_EXTENSION: {
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    }
}
WRITE_TOOL = {
    MCP_ANNOTATIONS_EXTENSION: {
        "readOnlyHint": False,
        "idempotentHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
    }
}
IDEMPOTENT_WRITE_TOOL = {
    MCP_ANNOTATIONS_EXTENSION: {
        "readOnlyHint": False,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    }
}
DESTRUCTIVE_TOOL = {
    MCP_ANNOTATIONS_EXTENSION: {
        "readOnlyHint": False,
        "idempotentHint": True,
        "destructiveHint": True,
        "openWorldHint": False,
    }
}


async def _forward_auth_header(request: httpx.Request) -> None:
    """Httpx request hook: forward the incoming MCP request's ``Authorization`` header.

    fastmcp's ``OpenAPITool.run`` already auto-forwards request headers, but
    its default exclude list strips ``authorization`` (see
    ``fastmcp.server.dependencies.get_http_headers``). We re-add it here so
    the route's ``Depends(authorize)`` can validate the user's bearer token.
    """
    from fastmcp.server.dependencies import get_http_headers

    auth_headers = get_http_headers(include={"authorization"})
    for key, value in auth_headers.items():
        if key not in request.headers:
            request.headers[key] = value


def _humanize(name: str) -> str:
    """Turn an ``operation_id`` into a human-readable tool title.

    ``get_process_status`` -> ``Get Process Status``.
    """
    return name.replace("_", " ").title()


def _build_component_fn(app: FastAPI) -> Any:
    """Return a fastmcp ``mcp_component_fn`` that applies per-route ``ToolAnnotations``.

    Builds an ``operation_id -> x-mcp-annotations`` lookup from the app's OpenAPI
    spec (where each route's ``openapi_extra`` hints land verbatim), then returns a
    callback fastmcp invokes per generated tool. Each tool's ``annotations`` are
    built from its route's hints, defaulting ``title`` to a humanized operation_id.

    The lookup is sourced from ``app.openapi()`` rather than by walking
    ``app.routes``: as of FastAPI 0.138 ``include_router`` mounts routes lazily
    behind an internal ``_IncludedRouter`` wrapper, so ``app.routes`` no longer
    yields the included ``APIRoute`` objects. The OpenAPI spec is the stable,
    public surface that carries both the ``operationId`` and the ``x-mcp-annotations``
    extension.
    """
    from mcp.types import ToolAnnotations

    # Flatten ``paths -> {method: operation}`` into operation dicts; skip path-level
    # entries like ``parameters`` (a list) that aren't operations.
    operations = chain.from_iterable(methods.values() for methods in app.openapi()["paths"].values())
    hints_by_op_id: dict[str, dict[str, Any]] = {
        operation["operationId"]: operation[MCP_ANNOTATIONS_EXTENSION]
        for operation in operations
        if isinstance(operation, dict) and operation.get(MCP_ANNOTATIONS_EXTENSION) and operation.get("operationId")
    }

    def apply(route: Any, component: Any) -> None:
        name = getattr(component, "name", None)
        if not isinstance(name, str):
            return
        hints = hints_by_op_id.get(name)
        if hints is None:
            return
        data = {"title": _humanize(name), **hints}
        component.annotations = ToolAnnotations(**data)

    return apply


def build_mcp(app: FastAPI) -> "FastMCP":  # noqa: F821 (TYPE_CHECKING-only import; string annotation)
    """Construct the configured ``FastMCP`` for ``app`` without mounting it.

    Extracted so tests can build the exact same server (route maps, component
    customization, auth-forwarding hook) the application uses at runtime.
    """
    from fastmcp import FastMCP
    from fastmcp.server.providers.openapi import MCPType, RouteMap

    return FastMCP.from_fastapi(
        app=app,
        name="orchestrator-core-mcp",
        route_maps=[
            RouteMap(tags={AGENT_EXPOSED_TAG}, mcp_type=MCPType.TOOL),
            RouteMap(mcp_type=MCPType.EXCLUDE),
        ],
        mcp_component_fn=_build_component_fn(app),
        httpx_client_kwargs={"event_hooks": {"request": [_forward_auth_header]}},
    )


def mount_mcp(app: FastAPI) -> Starlette:
    """Auto-generate MCP tools from ``app``'s routes, mount at ``/mcp``, return the sub-app.

    Only routes tagged with ``AGENT_EXPOSED_TAG`` are surfaced; all other
    routes are excluded (otherwise fastmcp's default would expose every
    route in the app as a tool).

    The returned sub-app carries its own ASGI lifespan that the parent must
    enter — Starlette does not invoke a mounted sub-app's lifespan. Use
    ``mcp_app.router.lifespan_context(parent)`` from inside the parent's
    own lifespan context manager.
    """
    mcp = build_mcp(app)
    mcp_app = mcp.http_app(path="/", transport="http")
    app.mount(MCP_MOUNT_PATH, mcp_app)
    return mcp_app

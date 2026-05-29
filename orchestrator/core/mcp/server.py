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
``AgentTag.EXPOSED`` becomes an MCP tool with a typed parameter schema
derived from the route's pydantic models, plus the route's docstring as the
tool description.

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

from typing import TYPE_CHECKING

import httpx
from fastapi import FastAPI
from starlette.applications import Starlette

from orchestrator.core.agent_tags import AgentTag

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from fastmcp.utilities.openapi import HTTPRoute

MCP_MOUNT_PATH = "/mcp"


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


def _annotate(route: "HTTPRoute", component: object) -> None:
    """Stamp ``ToolAnnotations`` on each generated tool (``mcp_component_fn`` hook).

    Read/idempotent/destructive hints are inferred from the HTTP method, with
    ``AgentTag.READONLY`` / ``AgentTag.DESTRUCTIVE`` overriding for POST/PUT
    routes that don't follow method semantics (e.g. the curated POST read
    tools). ``openWorldHint`` is always ``False`` — the orchestrator operates
    on its own database, not an open external world.
    """
    from fastmcp.server.providers.openapi import OpenAPITool
    from mcp.types import ToolAnnotations

    if not isinstance(component, OpenAPITool):
        return

    tags = set(route.tags)
    method = route.method.upper()
    read_only = method == "GET" or AgentTag.READONLY.value in tags
    destructive = method == "DELETE" or AgentTag.DESTRUCTIVE.value in tags
    component.annotations = ToolAnnotations(
        title=_humanize(component.name),
        readOnlyHint=read_only,
        idempotentHint=read_only or method in {"PUT", "DELETE"},
        destructiveHint=destructive,
        openWorldHint=False,
    )


def build_mcp(app: FastAPI) -> "FastMCP":  # noqa: F821 (lazy import below)
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
            RouteMap(tags={AgentTag.EXPOSED.value}, mcp_type=MCPType.TOOL),
            RouteMap(mcp_type=MCPType.EXCLUDE),
        ],
        mcp_component_fn=_annotate,
        httpx_client_kwargs={"event_hooks": {"request": [_forward_auth_header]}},
    )


def mount_mcp(app: FastAPI) -> Starlette:
    """Auto-generate MCP tools from ``app``'s routes, mount at ``/mcp``, return the sub-app.

    Only routes tagged with ``AgentTag.EXPOSED`` are surfaced; all other
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

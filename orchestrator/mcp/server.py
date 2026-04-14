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

"""MCP server setup for orchestrator-core.

This module creates the ``FastMCP`` instance and exposes the factory
functions used to mount the MCP server into the parent FastAPI application.

Tool definitions live in ``orchestrator.mcp.tools``.  That module is imported
here as a side-effect so that all ``@mcp.tool()`` decorators run and register
their tools on the shared ``mcp`` instance before the ASGI app is built.
"""

from typing import Any

import structlog
from fastmcp import FastMCP

logger = structlog.get_logger(__name__)

mcp = FastMCP(
    name="orchestrator-core",
    instructions=(
        "Orchestrator Core MCP Server. Provides tools for managing network "
        "automation workflows, processes, subscriptions, and products. "
        "Use list_workflows() to discover available workflows, "
        "get_workflow_form() to inspect required form fields before starting, "
        "and create_workflow() to start a workflow process."
    ),
)

# Side-effect import: registers all @mcp.tool() decorated functions defined
# in tools.py onto the mcp instance above.
import orchestrator.mcp.tools as _tools  # noqa: E402, F401


def create_mcp_server() -> FastMCP:
    """Return the configured MCP server instance.

    Returns:
        FastMCP: Configured MCP server instance ready to be mounted.
    """
    return mcp


def create_mcp_app(auth_manager: Any = None) -> Any:
    """Create the MCP ASGI app for mounting in FastAPI.

    Returns a StarletteWithLifespan instance. Lifespan is managed
    automatically by Starlette's mount() lifespan forwarding (Starlette ≥0.37).

    Args:
        auth_manager: The AuthManager instance from the parent OrchestratorCore.
            If provided, all MCP requests will require valid Bearer token
            authentication using the same pluggable auth backend as the REST API.
            If None, the MCP server runs without authentication (development only).

    Returns:
        StarletteWithLifespan: The MCP ASGI app, optionally configured with
        authentication middleware.
    """
    mcp_app = mcp.http_app(path="/")

    if auth_manager is not None:
        from orchestrator.mcp.auth import MCPAuthMiddleware

        mcp_app.add_middleware(MCPAuthMiddleware, auth_manager=auth_manager)
        logger.info("MCP server configured with authentication middleware")
    else:
        logger.warning("MCP server running WITHOUT authentication")

    return mcp_app

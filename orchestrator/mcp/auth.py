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

"""Authentication middleware for the MCP server.

Wraps the MCP ASGI application with Bearer token authentication using
the orchestrator's pluggable AuthManager. The auth_manager is passed
by closure from the parent OrchestratorCore app, avoiding the need
to access request.app.auth_manager (which doesn't work in sub-apps).
"""

from http import HTTPStatus
from typing import Any

import structlog
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from orchestrator.core.security import http_bearer_extractor

logger = structlog.get_logger(__name__)


class MCPAuthMiddleware:
    """ASGI middleware that authenticates and authorizes MCP requests using the orchestrator's AuthManager.

    This middleware extracts Bearer tokens from the Authorization header using the same
    ``HttpBearerExtractor`` that protects the REST API, then validates them through the
    same ``auth_manager.authentication.authenticate`` and ``auth_manager.authorization.authorize``
    call chain used by the ``authenticate`` and ``authorize`` FastAPI dependencies in
    ``orchestrator/core/security.py``.

    The auth_manager is injected via the constructor (closure pattern) rather than accessed
    via request.app, since mounted sub-apps don't share the parent's app instance.

    The authenticated OIDCUserModel is stored in scope["state"]["mcp_user"] so that
    MCP tool functions can access it for audit logging and RBAC.

    Args:
        app: The inner ASGI application (FastMCP http_app).
        auth_manager: The AuthManager instance from the parent OrchestratorCore.
    """

    def __init__(self, app: ASGIApp, auth_manager: Any) -> None:
        self.app = app
        self.auth_manager = auth_manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only authenticate HTTP requests; lifespan and other ASGI scope types pass through
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Extract bearer token using the same HttpBearerExtractor used by the REST API.
        http_credentials = await http_bearer_extractor(request)
        token = http_credentials.credentials if http_credentials else None

        # Calls the same auth_manager.authentication.authenticate path used by the
        # `authenticate` FastAPI dependency in orchestrator/security.py.
        try:
            user = await self.auth_manager.authentication.authenticate(request, token)
        except Exception as e:
            logger.warning("MCP authentication failed", error=str(e))
            response = JSONResponse(
                status_code=HTTPStatus.UNAUTHORIZED,
                content={"error": "authentication_failed", "message": str(e)},
            )
            await response(scope, receive, send)
            return

        # Calls the same auth_manager.authorization.authorize path used by the
        # `authorize` FastAPI dependency in orchestrator/security.py.
        try:
            authorized = await self.auth_manager.authorization.authorize(request, user)
        except Exception as e:
            logger.warning("MCP authorization failed", error=str(e))
            response = JSONResponse(
                status_code=HTTPStatus.FORBIDDEN,
                content={"error": "authorization_failed", "message": str(e)},
            )
            await response(scope, receive, send)
            return

        # authorized=None means auth is disabled (OAUTH2_ACTIVE=False); treat as permitted.
        # authorized=False means the policy explicitly denied the request.
        if authorized is False:
            # OIDCUserModel guarantees .user_name attribute
            logger.debug("MCP request denied by authorization policy", user=user.user_name if user else "unknown")
            response = JSONResponse(
                status_code=HTTPStatus.FORBIDDEN,
                content={"error": "forbidden", "message": "Authorization policy denied the request"},
            )
            await response(scope, receive, send)
            return

        # Store authenticated user in scope state for tool access
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["mcp_user"] = user
        # OIDCUserModel guarantees .user_name attribute
        scope["state"]["mcp_user_name"] = user.user_name if user else "unknown"

        await self.app(scope, receive, send)

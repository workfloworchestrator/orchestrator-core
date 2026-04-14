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

logger = structlog.get_logger(__name__)


class MCPAuthMiddleware:
    """ASGI middleware that authenticates MCP requests using the orchestrator's AuthManager.

    This middleware extracts Bearer tokens from the Authorization header and validates
    them using the same pluggable OIDCAuth backend that protects the REST API. The
    auth_manager is injected via the constructor (closure pattern) rather than accessed
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
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        token = self._extract_bearer_token(request)

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

        # Store authenticated user in scope state for tool access
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["mcp_user"] = user
        scope["state"]["mcp_user_name"] = self._resolve_user_name(user)

        await self.app(scope, receive, send)

    @staticmethod
    def _extract_bearer_token(request: Request) -> str | None:
        """Extract Bearer token from the Authorization header."""
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        return None

    @staticmethod
    def _resolve_user_name(user: Any) -> str:
        """Resolve a display name from the OIDCUserModel, falling back to 'mcp'."""
        if user is None:
            return "mcp"
        if hasattr(user, "name") and user.name:
            return user.name
        if hasattr(user, "user_name") and user.user_name:
            return user.user_name
        return "mcp"

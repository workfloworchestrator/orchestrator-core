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

"""Unit tests for MCPAuthMiddleware.

Covers our auth middleware's decision logic:
- Missing/invalid token: returns 401 with JSON error
- authorized=None (auth disabled): passes through, user stored in scope
- authorized=True: passes through, user stored in scope
- authorized=False: returns 403 with JSON error
- authorize() raises: returns 403 with JSON error
"""

import json
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed; skipping MCP tests")

from orchestrator.mcp.auth import MCPAuthMiddleware  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_scope(path: str = "/") -> dict:
    """Build a minimal ASGI HTTP scope dict."""
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "query_string": b"",
        "headers": [],
        "state": {},
    }


def make_scope_with_auth(token: str, path: str = "/") -> dict:
    """Build an ASGI scope that carries a Bearer token in the Authorization header."""
    scope = make_scope(path)
    scope["headers"] = [
        (b"authorization", f"Bearer {token}".encode()),
        (b"content-type", b"application/json"),
    ]
    return scope


def make_auth_manager(
    authenticate_return=None,
    authenticate_side_effect=None,
    authorize_return=None,
    authorize_side_effect=None,
) -> MagicMock:
    """Build a mock auth_manager with async authenticate/authorize methods."""
    auth_manager = MagicMock()
    auth_manager.authentication.authenticate = AsyncMock(
        return_value=authenticate_return,
        side_effect=authenticate_side_effect,
    )
    auth_manager.authorization.authorize = AsyncMock(
        return_value=authorize_return,
        side_effect=authorize_side_effect,
    )
    return auth_manager


async def capture_messages(middleware, scope, receive) -> tuple[int, dict]:
    """Run middleware and return (status_code, parsed_body)."""
    messages: list[dict] = []

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    body_bytes = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return status, json.loads(body_bytes)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def inner_app() -> AsyncMock:
    """A mock inner ASGI app that records calls."""
    return AsyncMock()


# ── 401 scenarios ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("token,side_effect,description", [
    (None, Exception("No credentials provided"), "missing auth header"),
    ("bad.token.value", Exception("Token validation failed: signature mismatch"), "invalid token"),
])
async def test_authentication_failure_returns_401(inner_app, token, side_effect, description):
    """authenticate() raising must return 401 with authentication_failed error."""
    auth_manager = make_auth_manager(authenticate_side_effect=side_effect)
    middleware = MCPAuthMiddleware(inner_app, auth_manager=auth_manager)

    scope = make_scope_with_auth(token) if token else make_scope()
    receive = AsyncMock(return_value={"type": "http.request", "body": b""})

    fake_credentials = None
    if token:
        fake_credentials = MagicMock()
        fake_credentials.credentials = token

    with patch("orchestrator.mcp.auth.http_bearer_extractor", new=AsyncMock(return_value=fake_credentials)):
        status, body = await capture_messages(middleware, scope, receive)

    assert status == HTTPStatus.UNAUTHORIZED, f"Expected 401 for {description}"
    assert body["error"] == "authentication_failed"
    inner_app.assert_not_awaited()


# ── Passthrough scenarios (authorized=None and authorized=True) ────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("authorize_return,description", [
    (None, "auth disabled (authorized=None)"),
    (True, "authorized=True"),
])
async def test_auth_success_passes_through(inner_app, authorize_return, description):
    """Successful auth with authorized=None or True must call inner app and store user in scope."""
    mock_user = SimpleNamespace(user_name="alice")
    auth_manager = make_auth_manager(authenticate_return=mock_user, authorize_return=authorize_return)
    middleware = MCPAuthMiddleware(inner_app, auth_manager=auth_manager)

    scope = make_scope_with_auth("valid.token")
    receive = AsyncMock(return_value={"type": "http.request", "body": b""})
    send = AsyncMock()

    fake_credentials = MagicMock()
    fake_credentials.credentials = "valid.token"

    with patch("orchestrator.mcp.auth.http_bearer_extractor", new=AsyncMock(return_value=fake_credentials)):
        await middleware(scope, receive, send)

    inner_app.assert_awaited_once_with(scope, receive, send)
    assert scope["state"]["mcp_user"] is mock_user
    assert scope["state"]["mcp_user_name"] == "alice"


# ── 403 scenarios ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_success_authorized_false_returns_403(inner_app):
    """authorized=False must return 403 and NOT call the inner app."""
    mock_user = SimpleNamespace(user_name="dave")
    auth_manager = make_auth_manager(authenticate_return=mock_user, authorize_return=False)
    middleware = MCPAuthMiddleware(inner_app, auth_manager=auth_manager)

    scope = make_scope_with_auth("valid.token")
    receive = AsyncMock(return_value={"type": "http.request", "body": b""})

    fake_credentials = MagicMock()
    fake_credentials.credentials = "valid.token"

    with patch("orchestrator.mcp.auth.http_bearer_extractor", new=AsyncMock(return_value=fake_credentials)):
        status, body = await capture_messages(middleware, scope, receive)

    assert status == HTTPStatus.FORBIDDEN
    assert body["error"] == "forbidden"
    inner_app.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorization_exception_returns_403(inner_app):
    """When authorize() raises, the middleware must return 403."""
    mock_user = SimpleNamespace(user_name="eve")
    auth_manager = make_auth_manager(
        authenticate_return=mock_user,
        authorize_side_effect=RuntimeError("Policy engine unavailable"),
    )
    middleware = MCPAuthMiddleware(inner_app, auth_manager=auth_manager)

    scope = make_scope_with_auth("valid.token")
    receive = AsyncMock(return_value={"type": "http.request", "body": b""})

    fake_credentials = MagicMock()
    fake_credentials.credentials = "valid.token"

    with patch("orchestrator.mcp.auth.http_bearer_extractor", new=AsyncMock(return_value=fake_credentials)):
        status, body = await capture_messages(middleware, scope, receive)

    assert status == HTTPStatus.FORBIDDEN
    assert body["error"] == "authorization_failed"
    assert "Policy engine unavailable" in body["message"]
    inner_app.assert_not_awaited()



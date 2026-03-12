# Copyright 2019-2020 SURF, GÉANT.
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

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from oauth2_lib.fastapi import AuthManager
from oauth2_lib.settings import oauth2lib_settings
from orchestrator.security import AgentAuthMiddleware

# ---------------------------------------------------------------------------
# Mocking note — do NOT use MagicMock(spec=OIDCUserModel) as a user sentinel
# ---------------------------------------------------------------------------
# OIDCUserModel is a Pydantic v2 model and does not define __bool__.  When
# unittest.mock builds a MagicMock with a spec it only wires up the magic
# methods that are present on the spec class.  Because __bool__ is absent,
# the mock falls back to object.__bool__ which, for MagicMock instances with
# a spec, evaluates to False in certain CPython versions.  The net effect is
# that `if user:` inside AgentAuthMiddleware.__call__ would be False even
# though authenticate() returned a valid (mocked) user, causing a spurious
# 401.  Use a plain MagicMock() (no spec) so that its __bool__ is always True.
# ---------------------------------------------------------------------------


async def _ok(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


def _make_client(auth_manager: AuthManager) -> TestClient:
    inner = Starlette(routes=[Route("/", _ok)])
    return TestClient(AgentAuthMiddleware(inner, auth_manager), raise_server_exceptions=False)


def _make_auth_manager(user: object | None = None) -> MagicMock:
    auth_manager = MagicMock()
    auth_manager.authentication.authenticate = AsyncMock(return_value=user)
    auth_manager.authorization.authorize = AsyncMock(return_value=True)
    return auth_manager


@pytest.fixture(autouse=True)
def restore_oauth2_active():
    original = oauth2lib_settings.OAUTH2_ACTIVE
    yield
    oauth2lib_settings.OAUTH2_ACTIVE = original


def test_oauth2_inactive_bypasses_auth():
    """When OAUTH2_ACTIVE is False the middleware must pass through without touching auth_manager."""
    oauth2lib_settings.OAUTH2_ACTIVE = False
    auth_manager = _make_auth_manager()

    response = _make_client(auth_manager).get("/")

    assert response.status_code == HTTPStatus.OK
    assert response.text == "OK"
    auth_manager.authentication.authenticate.assert_not_called()
    auth_manager.authorization.authorize.assert_not_called()


def test_valid_token_passes_through():
    """When OAUTH2_ACTIVE is True and authentication succeeds, the request reaches the sub-app."""
    oauth2lib_settings.OAUTH2_ACTIVE = True
    user = MagicMock()
    auth_manager = _make_auth_manager(user=user)

    response = _make_client(auth_manager).get("/", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == HTTPStatus.OK
    auth_manager.authentication.authenticate.assert_awaited_once()
    auth_manager.authorization.authorize.assert_awaited_once()


def test_missing_token_returns_401():
    """When OAUTH2_ACTIVE is True and authentication returns None (no token), a 401 is returned."""
    oauth2lib_settings.OAUTH2_ACTIVE = True
    auth_manager = _make_auth_manager(user=None)

    response = _make_client(auth_manager).get("/")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Unauthorized"}


def test_auth_http_exception_is_forwarded():
    """An HTTPException raised by authenticate is converted to the matching HTTP response."""
    oauth2lib_settings.OAUTH2_ACTIVE = True
    auth_manager = _make_auth_manager()
    auth_manager.authentication.authenticate = AsyncMock(
        side_effect=HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Forbidden")
    )

    response = _make_client(auth_manager).get("/", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {"detail": "Forbidden"}


def test_bearer_token_is_extracted_and_passed_to_authenticate():
    """The raw token value (without the 'Bearer ' prefix) is forwarded to authenticate."""
    oauth2lib_settings.OAUTH2_ACTIVE = True
    user = MagicMock()
    auth_manager = _make_auth_manager(user=user)

    _make_client(auth_manager).get("/", headers={"Authorization": "Bearer my-secret-token"})

    _call_args = auth_manager.authentication.authenticate.call_args
    token_arg = _call_args.args[1] if len(_call_args.args) > 1 else _call_args.kwargs.get("token")
    assert token_arg == "my-secret-token"  # noqa: S105


def test_non_http_scope_bypasses_auth():
    """Lifespan and other non-http/websocket scopes must be forwarded without auth."""
    oauth2lib_settings.OAUTH2_ACTIVE = True
    auth_manager = _make_auth_manager()

    # TestClient exercises the lifespan scope automatically on enter/exit;
    # verify no auth calls are made during that lifecycle.
    with _make_client(auth_manager):
        pass

    auth_manager.authentication.authenticate.assert_not_called()
    auth_manager.authorization.authorize.assert_not_called()

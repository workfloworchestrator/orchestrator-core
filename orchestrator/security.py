# Copyright 2019-2026 SURF, GÉANT, ESnet.
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
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends
from fastapi.security.http import HTTPAuthorizationCredentials
from starlette.requests import Request
from starlette.websockets import WebSocket

from nwastdlib.url import URL
from oauth2_lib.fastapi import HTTPX_SSL_CONTEXT, HttpBearerExtractor, OIDCUserModel
from oauth2_lib.settings import oauth2lib_settings
from orchestrator.api.error_handling import raise_status

oauth_client_credentials = OAuth()

oauth_client_credentials.register(
    "connext",
    server_metadata_url=URL(oauth2lib_settings.OIDC_CONF_URL),
    client_id=oauth2lib_settings.OAUTH2_RESOURCE_SERVER_ID,
    client_secret=oauth2lib_settings.OAUTH2_RESOURCE_SERVER_SECRET,
    request_token_params={"grant_type": "client_credentials"},
    client_kwargs={"verify": HTTPX_SSL_CONTEXT},
)

http_bearer_extractor = HttpBearerExtractor(auto_error=False)


async def authenticate(
    request: Request,
    http_auth_credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer_extractor)] = None,
) -> OIDCUserModel | None:
    token = http_auth_credentials.credentials if http_auth_credentials else None
    return await request.app.auth_manager.authentication.authenticate(request, token)


async def authorize(request: Request, user: Annotated[OIDCUserModel | None, Depends(authenticate)]) -> bool | None:
    """FastAPI dependency (middleware) to determine if user is authorized to make a request.

    Must raise a 403 Forbidden in order to interrupt handling of request.

    OrchestratorCore.register_authorization allows users to register their own Authorization instance.
    This could be the oauth2_lib default OPA-based instance, but with auto_error=False,
    or a custom Authorization instance entirely. So we should be sure to raise on a False.

    True: authorized
    None: auth bypass
    False: not authorized, so raise
    HTTPException: allow this to raise
    """
    result = await request.app.auth_manager.authorization.authorize(request, user)
    if result is False:  # None is different!
        raise_status(HTTPStatus.FORBIDDEN, detail="Not authorized")

    # Either authorized (True) or authorization is bypassed (None)
    return result


async def authenticate_websocket(websocket: WebSocket, token: str) -> OIDCUserModel | None:
    return await websocket.app.auth_manager.authentication.authenticate(websocket, token)


async def authorize_websocket(
    websocket: WebSocket, user: Annotated[OIDCUserModel | None, Depends(authenticate)]
) -> bool | None:
    """FastAPI dependency (middleware) to determine if user is authorized to make a websocket connection.

    Must raise a 403 Forbidden in order to interrupt handling of request.

    OrchestratorCore.register_graphql_authorization allows users to register their own GraphQLAuthorization
    instance. This could be the oauth2_lib default OPA-based instance, but with auto_error=False,
    or a custom GraphQLAuthorization instance entirely. So we should be sure to raise on a False.

    True: authorized
    None: auth bypass
    False: not authorized, so raise
    HTTPException: allow this to raise
    """
    result = await websocket.app.auth_manager.authorization.authorize(websocket, user)
    if result is False:  # None is different!
        raise_status(HTTPStatus.FORBIDDEN, detail="Not authorized")

    # Either authorized (True) or authorization is bypassed (None)
    return result

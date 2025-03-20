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
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends
from fastapi.security.http import HTTPAuthorizationCredentials
from starlette.requests import Request
from starlette.websockets import WebSocket

from nwastdlib.url import URL
from oauth2_lib.fastapi import HTTPX_SSL_CONTEXT, HttpBearerExtractor, OIDCUserModel
from oauth2_lib.settings import oauth2lib_settings

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
    return await request.app.auth_manager.authorization.authorize(request, user)


async def authenticate_websocket(websocket: WebSocket, token: str) -> OIDCUserModel | None:
    return await websocket.app.auth_manager.authentication.authenticate(websocket, token)


async def authorize_websocket(
    websocket: WebSocket, user: Annotated[OIDCUserModel | None, Depends(authenticate)]
) -> bool | None:
    return await websocket.app.auth_manager.authorization.authorize(websocket, user)

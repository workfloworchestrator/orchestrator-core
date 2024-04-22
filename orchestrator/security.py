# Copyright 2019-2020 SURF.
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
import importlib

import structlog
from authlib.integrations.starlette_client import OAuth

from oauth2_lib.fastapi import (
    HTTPX_SSL_CONTEXT,
    AuthenticationFunc,
    Authorization,
    AuthorizationFunc,
    GraphqlAuthorization,
    GraphqlAuthorizationFunc,
    OIDCAuth,
)
from oauth2_lib.settings import oauth2lib_settings
from orchestrator.settings import auth_settings

oauth_client_credentials = OAuth()

# TODO this can probably go to the orchestrator implementation? otherwise introduce env-var for "connext"
oauth_client_credentials.register(
    "connext",
    server_metadata_url=oauth2lib_settings.OIDC_CONF_URL,
    client_id=oauth2lib_settings.OAUTH2_RESOURCE_SERVER_ID,
    client_secret=oauth2lib_settings.OAUTH2_RESOURCE_SERVER_SECRET,
    request_token_params={"grant_type": "client_credentials"},
    client_kwargs={"verify": HTTPX_SSL_CONTEXT},
)

_oidc_auth = None
_authorization = None
_graphql_authorization = None

logger = structlog.get_logger()


def _get_authentication() -> OIDCAuth:
    module_path, instance_name = auth_settings.AUTHENTICATION_INSTANCE.rsplit(".", 1)
    logger.warning("Get authn instance", module_path=module_path, instance_name=instance_name)  # TODO remove
    module = importlib.import_module(module_path)
    auth_instance = getattr(module, instance_name)

    if not isinstance(auth_instance, OIDCAuth):
        raise TypeError(f"The instance {instance_name} is not a subclass of OIDCAuth")

    return auth_instance


def _get_authorization() -> Authorization:
    module_path, instance_name = auth_settings.AUTHORIZATION_INSTANCE.rsplit(".", 1)
    logger.warning("Get authz instance", module_path=module_path, instance_name=instance_name)  # TODO remove
    module = importlib.import_module(module_path)
    authorization_instance = getattr(module, instance_name)

    if not isinstance(authorization_instance, Authorization):
        raise TypeError(f"The instance {instance_name} is not a subclass of Authorization")

    return authorization_instance


def _get_graphql_authorization() -> GraphqlAuthorization:
    module_path, instance_name = auth_settings.GRAPHQL_AUTHORIZATION_INSTANCE.rsplit(".", 1)
    logger.warning("Get gql authz instance", module_path=module_path, instance_name=instance_name)  # TODO remove
    module = importlib.import_module(module_path)
    authorization_instance = getattr(module, instance_name)

    if not isinstance(authorization_instance, GraphqlAuthorization):
        raise TypeError(f"The instance {instance_name} is not a subclass of GraphqlAuthorization")

    return authorization_instance


def get_oidc_authentication() -> OIDCAuth:
    global _oidc_auth

    if not _oidc_auth:
        _oidc_auth = _get_authentication()

    return _oidc_auth


def get_authorization() -> Authorization:
    global _authorization

    if not _authorization:
        _authorization = _get_authorization()

    return _authorization


def get_graphql_authorization() -> GraphqlAuthorization:
    global _graphql_authorization

    if not _graphql_authorization:
        _graphql_authorization = _get_graphql_authorization()

    return _graphql_authorization


def get_oidc_authentication_function() -> AuthenticationFunc:
    oidc_auth = get_oidc_authentication()
    func = oidc_auth.authenticate
    logger.warning("Returning authn func", obj=oidc_auth, func=func)  # TODO remove
    return func


def get_authorization_function() -> AuthorizationFunc:
    authorization = get_authorization()
    func = authorization.authorize
    logger.warning("Returning authz func", obj=authorization, func=func)  # TODO remove
    return func  # type: ignore  # TODO fix AuthorizationFunc type


def get_graphql_authorization_function() -> GraphqlAuthorizationFunc:
    authorization = get_graphql_authorization()
    func = authorization.authorize
    logger.warning("Returning gql authz func", obj=authorization, func=func)  # TODO remove
    return func

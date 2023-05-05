# Copyright 2022-2023 SURF.
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
from typing import Any, Callable, Union

import strawberry
import structlog
from fastapi import HTTPException
from graphql.pyutils import Path
from strawberry import BasePermission
from strawberry.types import Info
from strawberry.types.fields.resolver import StrawberryResolver

from orchestrator.settings import app_settings, oauth2_settings

logger = structlog.get_logger(__name__)

# Note: if this becomes generic enough we might want to move this to oauth2_lib, so it can be reused also by
# other graphql providers (nwd-api, CIM, etc.)


def get_path_as_string(path: Path) -> str:
    if path.prev:
        return f"{get_path_as_string(path.prev)}/{path.key}"
    else:
        return f"{path.key}"


class IsAuthenticated(BasePermission):
    message = "User is not authenticated"

    async def has_permission(self, source: Any, info: Info, **kwargs) -> bool:  # type: ignore
        if not oauth2_settings.OAUTH2_ACTIVE:
            return True

        path = f"/{app_settings.SERVICE_NAME}/{get_path_as_string(info.path)}/".lower()

        context = info.context
        try:
            logger.debug("Request headers", headers=info.context.request.headers)
            current_user = await context.get_current_user(info.context.request)
        except HTTPException:
            self.message = f"User is not authorized to query or has an invalid access token for path: `{path}`"
            return False

        opa_decision = await context.get_opa_decision(path, current_user)

        logger.debug("Get opa decision", path=path, opa_decision=opa_decision)
        if not opa_decision:
            self.message = f"User is not authorized to query `{path}`"

        return opa_decision


class IsAuthenticatedForMutation(BasePermission):
    message = "User is not authenticated"

    async def has_permission(self, source: Any, info: Info, **kwargs) -> bool:  # type: ignore
        mutations_active = oauth2_settings.OAUTH2_ACTIVE and app_settings.MUTATIONS_ENABLED

        if not mutations_active:
            return app_settings.ENVIRONMENT in app_settings.ENVIRONMENT_IGNORE_MUTATION_DISABLED

        path = f"{app_settings.SERVICE_NAME}/{info.path.key}"
        try:
            current_user = await info.context.get_current_user(info.context.request)
        except HTTPException:
            self.message = f"User is not authorized to query or has an invalid access token for path: `{path}`"
            return False
        opa_decision: bool = await info.context.get_opa_decision(path, current_user)

        logger.debug("Get opa decision", path=path, opa_decision=opa_decision)
        if not opa_decision:
            self.message = f"User is not authorized to execute mutation `{path}`"

        return opa_decision


def authenticated_field(
    description: str,
    resolver: Union[StrawberryResolver, Callable, staticmethod, classmethod, None] = None,
    deprecation_reason: Union[str, None] = None,
) -> Any:
    return strawberry.field(
        description=description,
        resolver=resolver,  # type: ignore
        deprecation_reason=deprecation_reason,
        permission_classes=[IsAuthenticated],
    )


def authenticated_federated_field(  # type: ignore
    description: str,
    resolver: Union[StrawberryResolver, Callable, staticmethod, classmethod, None] = None,
    deprecation_reason: Union[str, None] = None,
    requires: Union[list[str], None] = None,
    **kwargs,
) -> Any:
    return strawberry.federation.field(
        description=description,
        resolver=resolver,  # type: ignore
        deprecation_reason=deprecation_reason,
        permission_classes=[IsAuthenticated],
        requires=requires,
        **kwargs,
    )

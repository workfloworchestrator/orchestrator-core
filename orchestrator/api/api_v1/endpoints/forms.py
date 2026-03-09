# Copyright 2019-2025 SURF.
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
from typing import Annotated, Any

import structlog
from fastapi import Depends
from fastapi.routing import APIRouter
from surf_auth_lib import SurfOIDCUserModel, authenticate

from pydantic_forms.core.asynchronous import start_form

logger = structlog.get_logger(__name__)

router: APIRouter = APIRouter()


@router.post("/{form_key}", status_code=HTTPStatus.CREATED)
async def new_form(
    form_key: str,
    json_data: list[dict[str, Any]],
    user: Annotated[SurfOIDCUserModel | None, Depends(authenticate)],
) -> dict[str, Any]:
    username = user.user_name if user else ""
    return await start_form(form_key, user_inputs=json_data, user=username)

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

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.error_handling import raise_status
from orchestrator.security import authenticate
from pydantic_forms.core.asynchronous import start_form
from pydantic_forms.exceptions import FormException

logger = structlog.get_logger(__name__)

router: APIRouter = APIRouter()


@router.post("/{form_key}", status_code=HTTPStatus.CREATED)
async def new_form(
    form_key: str,
    json_data: list[dict[str, Any]],
    user_model: Annotated[OIDCUserModel | None, Depends(authenticate)],
) -> dict[str, Any]:
    username = user_model.user_name if user_model else ""
    try:
        return await start_form(form_key, user_inputs=json_data, user=username)
    except FormException as exc:
        if "does not exist" in str(exc):
            return raise_status(HTTPStatus.NOT_FOUND, str(exc))
        raise exc

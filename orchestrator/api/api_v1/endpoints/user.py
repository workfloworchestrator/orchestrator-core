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

"""Module that implements user (e.g. miscellaneous) related API endpoints."""

from typing import Any

import structlog
from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from orchestrator.utils.json import json_loads

logger = structlog.get_logger(__name__)


router = APIRouter()


@router.post("/error", response_model=dict)
def log_error(data: dict[Any, Any] = Body(...)) -> dict:
    logger.error("Client reported an error", data=data, frontend_error=True)
    return {}


@router.post("/log/{user_name}", response_model=dict)
def log_user_info(user_name: str, message: dict = Body(...)) -> dict:
    """Log frontend messages that are related to user actions.

    When the frontend finalizes the setup of a login session it will do a HTTP POST to this endpoint. The frontend
    will also post to this endpoint when it ends a user session.

    Args:
        user_name: the username (email) of the user involved
        message: A log message.

    Returns:
        {}

    """
    try:
        json_dict: Any = json_loads(str(message))
        _message = json_dict["message"]
    except Exception:
        _message = message
    logger.info("Client sent user info", message=_message, user_name=user_name)
    return {}

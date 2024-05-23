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

"""Module that implements websocket endpoints."""

from typing import Annotated

import structlog
from fastapi import Header, status
from fastapi.routing import APIRouter
from fastapi.websockets import WebSocket

from orchestrator.settings import app_settings
from orchestrator.websocket import WS_CHANNELS, websocket_manager

logger = structlog.get_logger(__name__)

router = APIRouter()


WEBSOCKET_AUTH_SUBPROTOCOL = "base64.bearer.token"


class WebsocketAuthError(ValueError):
    pass


async def get_subprotocol_and_token(sec_websocket_protocol: str | None) -> tuple[str | None, str]:
    if not sec_websocket_protocol:
        return None, ""

    try:
        subprotocol, token = sec_websocket_protocol.split(", ")
    except ValueError:
        raise WebsocketAuthError("Sec-Websocket-Protocol should contain subprotocol and token separated by a comma")

    if subprotocol != WEBSOCKET_AUTH_SUBPROTOCOL:
        raise WebsocketAuthError(f"Sec-Websocket-Protocol subprotocol should be {WEBSOCKET_AUTH_SUBPROTOCOL}")

    return subprotocol, token


if app_settings.ENABLE_WEBSOCKETS:

    @router.websocket("/events")
    async def websocket_events(
        websocket: WebSocket, sec_websocket_protocol: Annotated[str | None, Header()] = None
    ) -> None:
        """Emits events for the frontend.

        Events are of the form {"name": <name>, "value": <value>}.
        To authenticate, provide an array [<WEBSOCKET_AUTH_SUBPROTOCOL>, <JWT token>] in the "Sec-Websocket-Protocol" header.
        """
        try:
            subprotocol, token = await get_subprotocol_and_token(sec_websocket_protocol)
        except WebsocketAuthError as exc:
            logger.info("Reject websocket client with invalid authentication", error=str(exc))
            await websocket_manager.disconnect(websocket, code=status.WS_1002_PROTOCOL_ERROR)
            return

        error = await websocket_manager.authorize(websocket, token)

        await websocket.accept(subprotocol=subprotocol)
        if error:
            await websocket_manager.disconnect(websocket, reason=error, code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket_manager.connect(websocket, WS_CHANNELS.EVENTS)

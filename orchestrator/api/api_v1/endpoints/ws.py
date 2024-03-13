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

if app_settings.ENABLE_WEBSOCKETS:

    @router.websocket("/events")
    async def websocket_events(
        websocket: WebSocket, sec_websocket_protocol: Annotated[str | None, Header()] = None
    ) -> None:
        """Emits events for the frontend.

        Events are of the form {"name": <name>, "value": <value>}.
        To authenticate, provide a JWT token in the "Sec-Websocket-Protocol" header.
        """
        error = await websocket_manager.authorize(websocket, sec_websocket_protocol or "")

        await websocket.accept()
        if error:
            await websocket_manager.disconnect(websocket, reason=error, code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket_manager.connect(websocket, WS_CHANNELS.EVENTS)

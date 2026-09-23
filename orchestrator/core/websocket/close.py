# Copyright 2019-2026 SURF, GÉANT.
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

from contextlib import suppress

from fastapi import WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from orchestrator.core.utils.json import json_dumps


async def close_websocket_safely(
    websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: dict | str | None = None
) -> None:
    """Close a websocket, tolerating a peer that is already gone. Never raises.

    Guards on ``application_state``, which is what starlette's ``send()`` checks; it goes
    DISCONNECTED while ``client_state`` stays CONNECTED when a send fails rather than the client
    disconnecting. The close races the peer going away regardless, so a socket closed underneath
    us raises rather than returning, and that is suppressed.
    """
    if websocket.application_state == WebSocketState.DISCONNECTED:
        return
    with suppress(RuntimeError, WebSocketDisconnect):
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code=code)

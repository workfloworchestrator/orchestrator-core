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


from collections.abc import Iterable
from contextlib import suppress
from itertools import chain

from fastapi import WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState
from structlog import get_logger

from orchestrator.core.utils.json import json_dumps

logger = get_logger(__name__)


class MemoryWebsocketManager:
    def __init__(self) -> None:
        self.connections_by_pid: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        if channel not in self.connections_by_pid:
            self.connections_by_pid[channel] = [websocket]
        else:
            self.connections_by_pid[channel].append(websocket)
        self.log_amount_of_connections()

        try:
            while True:
                message = await websocket.receive_text()
                if message == "__ping__":
                    await websocket.send_text("__pong__")
        except WebSocketDisconnect:
            pass
        await self.remove_ws(websocket, channel)

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: dict | str | None = None
    ) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code=code)

    def _connections(self, channels: Iterable[str]) -> list[tuple[str, WebSocket]]:
        """Snapshot of (channel, websocket) pairs, safe to iterate while remove_ws mutates the registry."""
        return list(
            chain.from_iterable(
                ((channel, websocket) for websocket in self.connections_by_pid.get(channel, []))
                for channel in list(channels)
            )
        )

    async def disconnect_all(self) -> None:
        for channel, websocket in self._connections(self.connections_by_pid):
            await self.remove_ws(websocket, channel)

    async def _send_text(self, websocket: WebSocket, payload: str) -> bool:
        """Send to one client; False when the connection is gone and the client should be dropped."""
        try:
            await websocket.send_text(payload)
        except (RuntimeError, ValueError, WebSocketDisconnect):
            return False
        return True

    async def broadcast_data(self, channels: list[str], data: dict) -> None:
        payload = json_dumps(data)
        # Drop clients the send failed on, plus everyone when the message closes the channel. Failing
        # one client must not abort the broadcast to the others.
        stale = [
            (channel, websocket)
            for channel, websocket in self._connections(channels)
            if not await self._send_text(websocket, payload) or data.get("close")
        ]
        for channel, websocket in stale:
            await self.remove_ws(websocket, channel)

    async def remove_ws(self, websocket: WebSocket, channel: str) -> None:
        # Guard on application_state, which is what starlette's send() checks. It goes DISCONNECTED
        # while client_state stays CONNECTED when a send fails rather than the client disconnecting,
        # and closing then raises. Suppress as well: the close itself races with the peer going away,
        # and the registry must be cleaned up either way.
        if websocket.application_state != WebSocketState.DISCONNECTED:
            with suppress(RuntimeError, WebSocketDisconnect):
                await self.disconnect(websocket)
        if channel in self.connections_by_pid and websocket in self.connections_by_pid[channel]:
            self.connections_by_pid[channel].remove(websocket)
            if not len(self.connections_by_pid[channel]):
                del self.connections_by_pid[channel]
        self.log_amount_of_connections()

    def log_amount_of_connections(self) -> None:
        amount = sum(len(channel) for channel in self.connections_by_pid.values())
        logger.info("Websocket Connections: %s", amount)

    async def connect_redis(self) -> None:
        pass

    async def disconnect_redis(self) -> None:
        pass

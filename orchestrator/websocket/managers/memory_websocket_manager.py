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


from fastapi import WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState
from structlog import get_logger

from orchestrator.utils.json import json_dumps

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

    async def disconnect_all(self) -> None:
        for channel in self.connections_by_pid:
            for websocket in self.connections_by_pid[channel]:
                await self.remove_ws(websocket, channel)

    async def broadcast_data(self, channels: list[str], data: dict) -> None:
        try:
            for channel in channels:
                if channel in self.connections_by_pid:
                    for websocket in self.connections_by_pid[channel]:
                        await websocket.send_text(json_dumps(data))
                        if "close" in data and data["close"]:
                            await self.remove_ws(websocket, channel)
        except (RuntimeError, ValueError):
            pass

    async def remove_ws(self, websocket: WebSocket, channel: str) -> None:
        if websocket.client_state != WebSocketState.DISCONNECTED:
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

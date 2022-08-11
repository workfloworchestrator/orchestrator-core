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

from typing import Dict, List, Union

from broadcaster import Broadcast
from fastapi import WebSocket, status
from starlette.concurrency import run_until_first_complete
from structlog import get_logger

from orchestrator.utils.json import json_dumps, json_loads

logger = get_logger(__name__)


class BroadcastWebsocketManager:
    def __init__(self, broadcast_url: str):
        self.connected: list[WebSocket] = []
        self.sub_broadcast = Broadcast(broadcast_url)
        self.pub_broadcast = Broadcast(broadcast_url)

    async def connect_redis(self) -> None:
        await self.sub_broadcast.connect()

    async def disconnect_redis(self) -> None:
        await self.sub_broadcast.disconnect()

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        self.connected.append(websocket)
        self.log_amount_of_connections()
        try:
            await run_until_first_complete(
                (self.sender, {"websocket": websocket, "channel": channel}),
                (self.receiver, {"websocket": websocket, "channel": channel}),
            )
        except Exception:  # noqa: S110
            pass
        self.remove_ws_from_connected_list(websocket)

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: Union[Dict, str, None] = None
    ) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code)
        self.remove_ws_from_connected_list(websocket)

    async def disconnect_all(self) -> None:
        for websocket in self.connected:
            await self.disconnect(websocket)

    async def receiver(self, websocket: WebSocket, channel: str) -> None:
        async for message in websocket.iter_text():
            if message == "__ping__":
                await websocket.send_text("__pong__")

    async def sender(self, websocket: WebSocket, channel: str) -> None:
        async with self.sub_broadcast.subscribe(channel=channel) as subscriber:
            async for event in subscriber:
                await websocket.send_text(event.message)

                json = json_loads(event.message)
                if type(json) is dict and "close" in json and json["close"] and channel != "processes":
                    await self.disconnect(websocket)
                    break

    async def broadcast_data(self, channels: List[str], data: Dict) -> None:
        await self.pub_broadcast.connect()
        for channel in channels:
            await self.pub_broadcast.publish(channel, message=json_dumps(data))
        await self.pub_broadcast.disconnect()

    def remove_ws_from_connected_list(self, websocket: WebSocket) -> None:
        if websocket in self.connected:
            self.connected.remove(websocket)
        self.log_amount_of_connections()

    def log_amount_of_connections(self) -> None:
        logger.info("Websocket Connections: %s", len(self.connected))

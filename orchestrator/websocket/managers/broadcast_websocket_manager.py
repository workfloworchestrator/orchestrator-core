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
from typing import Any

from fastapi import WebSocket, status
from starlette.concurrency import run_until_first_complete
from structlog import get_logger

from orchestrator.utils.json import json_dumps
from orchestrator.utils.redis import RedisBroadcast

logger = get_logger(__name__)


class BroadcastWebsocketManager:
    def __init__(self, broadcast_url: str):
        self.connected: list[WebSocket] = []
        self.broadcast_url = broadcast_url
        self.broadcast = RedisBroadcast(broadcast_url)

    async def connect_redis(self) -> None:
        await self.broadcast.connect()

    async def disconnect_redis(self) -> None:
        await self.broadcast.disconnect()

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Connect a new websocket client."""
        self.connected.append(websocket)
        log = logger.bind(client=websocket.client, channel=channel)
        log.debug("Websocket client connected, start loop", total_connections=len(self.connected))
        try:
            await run_until_first_complete(
                (self.sender, {"websocket": websocket, "channel": channel}),
                (self.receiver, {"websocket": websocket, "channel": channel}),
            )
        except Exception as exc:  # noqa: S110
            log.info("Websocket client loop stopped with an exception", message=str(exc))
        else:
            log.debug("Websocket client loop stopped normally")
        self.remove_ws_from_connected_list(websocket)

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: dict | str | None = None
    ) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code)
        self.remove_ws_from_connected_list(websocket)

    async def disconnect_all(self) -> None:
        for websocket in self.connected:
            await self.disconnect(websocket, code=status.WS_1001_GOING_AWAY, reason="Shutting down")

    async def receiver(self, websocket: WebSocket, channel: str) -> None:
        """Read messages from websocket client."""
        log = logger.bind(client=websocket.client, channel=channel)
        while True:
            try:
                message = await websocket.receive_text()
                log.debug("Received websocket message", message=repr(message))
            except Exception as exc:
                log.debug("Exception while reading from websocket client", msg=str(exc))
                break
            if message == "__ping__":
                await websocket.send_text("__pong__")

    async def sender(self, websocket: WebSocket, channel: str) -> None:
        """Read messages from redis channel and send to websocket client."""
        log = logger.bind(client=websocket.client, channel=channel)

        def parse_message(raw_message: Any) -> str | None:
            match raw_message:
                case {"type": "message", "data": bytes() as data}:
                    return data.decode()
                case None:
                    return None
                case _:
                    log.info("Drop unrecognized message", raw=raw_message)
                    return None

        async with self.broadcast.subscriber(channel) as subscriber:
            log.debug("Websocket client subscribed to channel")
            while True:
                raw = await subscriber.get_message(timeout=1)
                if (message := parse_message(raw)) is None:
                    continue

                log.debug("Send websocket message", message=message)
                await websocket.send_text(message)

    async def broadcast_data(self, channels: list[str], data: dict) -> None:
        """Send messages to redis channel.

        This can be called by API and/or Worker instances.
        """
        message = json_dumps(data)
        async with RedisBroadcast(self.broadcast_url).pipeline() as pipe:
            for channel in channels:
                pipe.publish(channel, message)

    def remove_ws_from_connected_list(self, websocket: WebSocket) -> None:
        if websocket in self.connected:
            self.connected.remove(websocket)
        logger.debug("Websocket client disconnected", total_connections=len(self.connected), client=websocket.client)

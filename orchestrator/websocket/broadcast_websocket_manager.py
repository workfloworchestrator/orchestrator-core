from typing import Dict, Union

from broadcaster import Broadcast
from fastapi import WebSocket, status
from starlette.concurrency import run_until_first_complete
from structlog import get_logger

from orchestrator.utils.json import json_dumps, json_loads

logger = get_logger(__name__)


class BroadcastWebsocketManager:
    def __init__(self, broadcast_url: str):
        self.sub_broadcast = Broadcast(broadcast_url)
        self.pub_broadcast = Broadcast(broadcast_url)
        self.connected = False

    async def connect_redis(self) -> None:
        if not self.connected:
            await self.sub_broadcast.connect()
            self.connected = True

    async def disconnect_redis(self) -> None:
        if self.connected:
            await self.sub_broadcast.disconnect()
            self.connected = False

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await self.connect_redis()  # necessary for unit tests
        try:
            await run_until_first_complete(
                (self.sender, {"websocket": websocket, "channel": channel}),
            )
        except Exception:  # noqa: S110
            pass

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: Union[Dict, str, None] = None
    ) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code)

    async def receiver(self, websocket: WebSocket, channel: str) -> None:
        async for message in websocket.iter_text():
            pass

    async def sender(self, websocket: WebSocket, channel: str) -> None:
        async with self.sub_broadcast.subscribe(channel=channel) as subscriber:
            async for event in subscriber:
                await websocket.send_text(event.message)

                json = json_loads(event.message)
                if type(json) is dict and "close" in json and json["close"] and channel != "processes":
                    await self.disconnect(websocket)
                    break

    async def broadcast_data(self, channel: str, data: Dict) -> None:
        await self.pub_broadcast.connect()
        await self.pub_broadcast.publish(channel, message=json_dumps(data))
        await self.pub_broadcast.disconnect()

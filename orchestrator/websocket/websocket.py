from typing import Dict, Optional, Union
from uuid import UUID

from broadcaster import Broadcast
from fastapi.exceptions import HTTPException
from fastapi.websockets import WebSocket
from httpx import AsyncClient
from starlette.concurrency import run_until_first_complete
from structlog import get_logger

from orchestrator.security import oidc_user, opa_security_default
from orchestrator.utils.json import json_dumps, json_loads

logger = get_logger(__name__)


class WebSocketManager:
    def __init__(self, broadcast_url: str):
        self.sub_broadcast = Broadcast(broadcast_url)
        self.pub_broadcast = Broadcast(broadcast_url)

    async def authorize(self, websocket: WebSocket, token: str) -> Optional[Dict]:
        try:
            async with AsyncClient() as client:
                user = await oidc_user(websocket, async_request=client, token=token)
                if user:
                    await opa_security_default(websocket, user, client)
        except HTTPException as e:
            return {"error": vars(e)}
        return None

    async def connect_redis(self) -> None:
        await self.sub_broadcast.connect()

    async def disconnect_redis(self) -> None:
        await self.sub_broadcast.disconnect()

    async def connect(self, websocket: WebSocket, pid: UUID) -> None:
        await run_until_first_complete(
            (self.sender, {"websocket": websocket, "pid": pid}),
        )

    async def disconnect(self, websocket: WebSocket, code: int = 1000, reason: Union[Dict, str, None] = None) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code)

    async def receiver(self, websocket: WebSocket, pid: UUID) -> None:
        async for message in websocket.iter_text():
            pass

    async def sender(self, websocket: WebSocket, pid: UUID) -> None:
        async with self.sub_broadcast.subscribe(channel=f"step_process:{pid}") as subscriber:
            async for event in subscriber:
                await websocket.send_text(event.message)

                json = json_loads(event.message)
                if "close" in json and json["close"]:
                    await self.disconnect(websocket)

    async def broadcast_data(self, channel: str, data: Dict) -> None:
        await self.pub_broadcast.connect()
        await self.pub_broadcast.publish(channel, message=json_dumps(data))
        await self.pub_broadcast.disconnect()

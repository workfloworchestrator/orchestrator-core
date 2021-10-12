from typing import Dict, Optional, Union
from urllib.parse import urlparse

from fastapi import WebSocket, status
from fastapi.exceptions import HTTPException
from httpx import AsyncClient
from structlog import get_logger

from orchestrator.security import oidc_user, opa_security_default
from orchestrator.websocket.broadcast_websocket_manager import BroadcastWebsocketManager
from orchestrator.websocket.memory_websocket_manager import MemoryWebsocketManager

logger = get_logger(__name__)


class WebSocketManager:
    _backend: Union[MemoryWebsocketManager, BroadcastWebsocketManager]

    def __init__(self, broadcast_url: str):
        self.broadcaster_type = urlparse(broadcast_url).scheme
        self.connected = False
        if self.broadcaster_type == "memory":
            self._backend = MemoryWebsocketManager()
        else:
            self._backend = BroadcastWebsocketManager(broadcast_url)

    async def authorize(self, websocket: WebSocket, token: str) -> Optional[Dict]:
        try:
            async with AsyncClient() as client:
                user = await oidc_user(websocket, async_request=client, token=token)  # type: ignore
                if user:
                    await opa_security_default(websocket, user, client)  # type: ignore
        except HTTPException as e:
            return {"error": vars(e)}
        return None

    async def connect_redis(self) -> None:
        if not self.connected:
            await self._backend.connect_redis()
            self.connected = True

    async def disconnect_redis(self) -> None:
        if self.connected:
            await self._backend.disconnect_redis()
            self.connected = False

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await self._backend.connect(websocket, channel)

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: Union[Dict, str, None] = None
    ) -> None:
        await self._backend.disconnect(websocket, code, reason)

    async def broadcast_data(self, channel: str, data: Dict) -> None:
        await self._backend.broadcast_data(channel, data)

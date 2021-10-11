from typing import Dict, List, Optional, Union

from fastapi import WebSocket, WebSocketDisconnect, status
from structlog import get_logger

from orchestrator.utils.json import json_dumps

logger = get_logger(__name__)


class MemoryWebsocketManager:
    def __init__(self) -> None:
        self.connections_by_pid: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        if channel not in self.connections_by_pid:
            self.connections_by_pid[channel] = [websocket]
        else:
            self.connections_by_pid[channel].append(websocket)

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: Union[Dict, str, None] = None
    ) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code=code)

    async def disconnect_all(self, channel: str, code: int = 1000, reason: Optional[Union[Dict, str]] = None) -> None:
        if channel in self.connections_by_pid:
            for connection in self.connections_by_pid[channel]:
                await self.disconnect(connection, code, reason)
                self.remove(connection, channel)

    def remove(self, websocket: WebSocket, channel: str) -> None:
        if channel in self.connections_by_pid:
            self.connections_by_pid[channel].remove(websocket)
            if len(self.connections_by_pid[channel]):
                del self.connections_by_pid[channel]

    async def broadcast_data(self, channel: str, data: Dict) -> None:
        try:
            if channel in self.connections_by_pid:
                for connection in self.connections_by_pid[channel]:
                    await connection.send_text(json_dumps(data))

            if "close" in data and data["close"]:
                await self.disconnect_all(channel)
        except (RuntimeError, ValueError):
            pass

    async def connect_redis(self) -> None:
        pass

    async def disconnect_redis(self) -> None:
        pass

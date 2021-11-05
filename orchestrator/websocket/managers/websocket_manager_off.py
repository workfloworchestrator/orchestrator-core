from typing import Dict, Optional, Union

from fastapi import WebSocket, status
from structlog import get_logger

logger = get_logger(__name__)


def broadcast_off_log(msg: str) -> None:
    msg = f"WebSocketManager: Websockets are turned off, {msg}"
    logger.warning(msg)


class WebsocketManagerOff:
    def __init__(self) -> None:
        broadcast_off_log("unable to init")

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        broadcast_off_log("unable to connect websocket")

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: Union[Dict, str, None] = None
    ) -> None:
        broadcast_off_log("unable to disconnect websocket")

    async def disconnect_all(self, channel: str, code: int = 1000, reason: Optional[Union[Dict, str]] = None) -> None:
        broadcast_off_log("unable to disconnect all websockets")

    def remove(self, websocket: WebSocket, channel: str) -> None:
        broadcast_off_log("unable to remove websocket")

    async def broadcast_data(self, channels: list[str], data: Dict) -> None:
        broadcast_off_log("unable to broadcast_data data")

    async def connect_redis(self) -> None:
        broadcast_off_log("unable to connect to redis")

    async def disconnect_redis(self) -> None:
        broadcast_off_log("unable to disconnect to redis")

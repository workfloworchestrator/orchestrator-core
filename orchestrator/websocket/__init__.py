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

from asyncio import new_event_loop
from functools import wraps
from typing import Any, Dict, Optional, cast
from urllib.parse import urlparse
from uuid import UUID

from structlog import get_logger

from orchestrator.db import ProcessTable
from orchestrator.settings import AppSettings, app_settings
from orchestrator.utils.show_process import show_process
from orchestrator.websocket.websocket_manager import WebSocketManager
from orchestrator.workflow import ProcessStat, ProcessStatus

logger = get_logger(__name__)


broadcaster_type = urlparse(app_settings.WEBSOCKET_BROADCASTER_URL).scheme


class WS_CHANNELS:
    ALL_PROCESSES = "processes"
    ENGINE_SETTINGS = "engine-settings"


async def empty_fn(*args: tuple, **kwargs: Dict[str, Any]) -> None:
    return


class WrappedWebSocketManager:
    def __init__(self, wrappee: Optional[WebSocketManager] = None) -> None:
        self.wrapped_websocket_manager = wrappee

    def update(self, wrappee: WebSocketManager) -> None:
        self.wrapped_websocket_manager = wrappee
        logger.warning("WebSocketManager object configured, all methods referencing `websocket_manager` should work.")

    def __getattr__(self, attr: str) -> Any:
        if not isinstance(self.wrapped_websocket_manager, WebSocketManager):
            if "_" in attr:
                logger.warning("No WebSocketManager configured, but attempting to access class methods")
                return
            raise RuntimeWarning(
                "No WebSocketManager configured at this time. Please pass WebSocketManager configuration to OrchestratorCore base_settings"
            )
        if attr != "enabled" and not self.wrapped_websocket_manager.enabled:
            logger.warning("Websockets are disabled, unable to access class methods")
            return empty_fn

        return getattr(self.wrapped_websocket_manager, attr)


# You need to pass a modified AppSettings class to the OrchestratorCore class to init the WebSocketManager correctly
wrapped_websocket_manager = WrappedWebSocketManager()
websocket_manager = cast(WebSocketManager, wrapped_websocket_manager)


# The Global WebSocketManager is set after calling this function
def init_websocket_manager(settings: AppSettings) -> WebSocketManager:
    wrapped_websocket_manager.update(WebSocketManager(settings.ENABLE_WEBSOCKETS, settings.WEBSOCKET_BROADCASTER_URL))
    return websocket_manager


def create_process_websocket_data(process: ProcessTable, pStat: ProcessStat) -> Dict:
    return {"process": show_process(process, pStat)}


def is_process_active(p: Dict) -> bool:
    return p["status"] in [ProcessStatus.RUNNING, ProcessStatus.SUSPENDED, ProcessStatus.WAITING]


def send_process_data_to_websocket(pid: UUID, data: Dict) -> None:
    loop = new_event_loop()
    channels = [WS_CHANNELS.ALL_PROCESSES]
    loop.run_until_complete(websocket_manager.broadcast_data(channels, data))
    try:
        loop.close()
    except Exception:  # noqa: S110
        pass


async def empty_handler() -> None:
    return


def websocket_enabled(handler: Any) -> Any:
    @wraps(handler)
    @wraps(empty_handler)
    async def wrapper(*args: tuple, **kwargs: Dict[str, Any]) -> Any:
        if websocket_manager.enabled:
            return await handler(*args, **kwargs)
        else:
            return await empty_handler()

    return wrapper


__all__ = [
    "websocket_manager",
    "init_websocket_manager",
    "create_process_websocket_data",
    "is_process_active",
    "send_process_data_to_websocket",
    "websocket_enabled",
    "WS_CHANNELS",
]

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
from typing import Any, Dict, Optional, cast
from urllib.parse import urlparse
from uuid import UUID

from structlog import get_logger

from orchestrator.db import ProcessStepTable, ProcessTable
from orchestrator.forms import generate_form
from orchestrator.settings import AppSettings, app_settings
from orchestrator.types import InputFormGenerator
from orchestrator.utils.show_process import show_process
from orchestrator.websocket.websocket_manager import WebSocketManager
from orchestrator.workflow import ProcessStatus

logger = get_logger(__name__)


broadcaster_type = urlparse(app_settings.WEBSOCKET_BROADCASTER_URL).scheme


class WS_CHANNELS:
    ALL_PROCESSES = "processes"

    @staticmethod
    def SINGLE_PROCESS(pid: UUID) -> str:
        return f"process_detail:{pid}"


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

        return getattr(self.wrapped_websocket_manager, attr)


# You need to pass a modified AppSettings class to the OrchestratorCore class to init the WebSocketManager correctly
wrapped_websocket_manager = WrappedWebSocketManager()
websocket_manager = cast(WebSocketManager, wrapped_websocket_manager)


# The Global WebSocketManager is set after calling this function
def init_websocket_manager(settings: AppSettings) -> WebSocketManager:
    wrapped_websocket_manager.update(WebSocketManager(settings.WEBSOCKET_BROADCASTER_URL))
    return websocket_manager


def create_process_step_websocket_data(
    process: ProcessTable, step: ProcessStepTable, step_form: Optional[InputFormGenerator]
) -> Dict:
    form = None
    if step_form:
        form = generate_form(step_form, step.state, [])

    return {
        "process": show_process(process),
        "step": {
            "name": step.name,
            "status": step.status,
            "state": step.state,
            "form": form,
        },
    }


def is_process_active(p: Dict) -> bool:
    return p["status"] in [ProcessStatus.RUNNING, ProcessStatus.SUSPENDED, ProcessStatus.WAITING]


def send_process_step_data_to_websocket(pid: UUID, data: Dict) -> None:
    channel = WS_CHANNELS.SINGLE_PROCESS(pid)

    if not is_process_active(data["process"]):
        data["close"] = True

    loop = new_event_loop()
    channels = [channel, WS_CHANNELS.ALL_PROCESSES]
    loop.run_until_complete(websocket_manager.broadcast_data(channels, data))
    try:
        loop.close()
    except Exception:  # noqa: S110
        pass


__all__ = [
    "websocket_manager",
    "init_websocket_manager",
    "create_websocket_data",
    "send_process_step_data_to_websocket",
    "is_process_active",
    "WS_CHANNELS",
]

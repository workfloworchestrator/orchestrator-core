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

from asyncio import new_event_loop, get_event_loop
from typing import Any, Optional, cast, Dict

from structlog import get_logger
from uuid import UUID
from orchestrator.settings import AppSettings
from orchestrator.websocket.websocket import WebSocketManager
from orchestrator.forms import generate_form
from orchestrator.db import ProcessTable, ProcessStepTable
from orchestrator.types import InputFormGenerator
from orchestrator.workflow import ProcessStatus

logger = get_logger(__name__)


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
    loop = get_event_loop()
    loop.run_until_complete(websocket_manager.connect_db())
    return websocket_manager


def create_process_step_websocket_data(process: ProcessTable, step: ProcessStepTable, step_form: Optional[InputFormGenerator]) -> Dict:
    form = None
    if step_form:
        form = generate_form(step_form, step.state, [])

    return {
        "process": {
            "assignee": process.assignee,
            "step": process.last_step,
            "status": process.last_status,
            "last_modified": process.last_modified_at,
        },
        "step": {
            "name": step.name,
            "status": step.status,
            "state": step.state,
            "form": form,
        },
    }


def send_process_step_data_to_websocket(pid: UUID, data: Dict) -> None:
    channel = f"step_process:{pid}"

    if data["process"]["status"] == ProcessStatus.COMPLETED:
        data["close"] = True

    loop = new_event_loop()
    loop.run_until_complete(websocket_manager.broadcast_data(channel, data))
    loop.close()


__all__ = [
    "websocket_manager",
    "init_websocket_manager",
    "create_websocket_data",
    "send_process_step_data_to_websocket",
]

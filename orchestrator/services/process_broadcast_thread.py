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
import asyncio
import queue
import threading
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import Request

from orchestrator.types import BroadcastFunc
from orchestrator.websocket import WS_CHANNELS
from orchestrator.websocket.websocket_manager import WebSocketManager

if TYPE_CHECKING:
    from orchestrator.graphql.types import OrchestratorInfo

logger = structlog.get_logger(__name__)


class ProcessDataBroadcastThread(threading.Thread):
    def __init__(self, _websocket_manager: WebSocketManager, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        self.shutdown = False
        self.queue: queue.Queue = queue.Queue()
        self.websocket_manager = _websocket_manager

    def run(self) -> None:
        logger.info("Starting ProcessDataBroadcastThread")
        try:
            loop = asyncio.new_event_loop()  # Create an eventloop specifically for this thread

            while not self.shutdown:
                try:
                    process_id, data = self.queue.get(block=True, timeout=1)
                except queue.Empty:
                    continue
                logger.debug(
                    "Threadsafe broadcast data through websocket manager",
                    process_id=process_id,
                    where="ProcessDataBroadcastThread",
                    channels=WS_CHANNELS.ALL_PROCESSES,
                )
                loop.run_until_complete(self.websocket_manager.broadcast_data([WS_CHANNELS.ALL_PROCESSES], data))

            loop.close()
            logger.info("Shutdown ProcessDataBroadcastThread")
        except Exception:
            logger.exception("Unhandled exception in ProcessDataBroadcastThread, exiting")

    def stop(self) -> None:
        logger.debug("Sending shutdown signal to ProcessDataBroadcastThread")
        self.shutdown = True
        self.join(timeout=5)
        self.is_alive()


def api_broadcast_process_data(request: Request) -> BroadcastFunc | None:
    """Given a FastAPI request, creates a threadsafe callable for broadcasting process data.

    The callable should be created in API endpoints and provided to start_process,
    resume_process, etc. through the `broadcast_func` param.
    """
    if not request.app.broadcast_thread:
        return None

    broadcast_queue: queue.Queue = request.app.broadcast_thread.queue

    def _queue_put(process_id: UUID, data: dict) -> None:
        broadcast_queue.put((str(process_id), data))

    return _queue_put


def graphql_broadcast_process_data(info: "OrchestratorInfo") -> BroadcastFunc | None:
    """Given a OrchestratorInfo, creates a threadsafe callable for broadcasting process data.

    The callable should be created in Graphql resolvers and provided to start_process,
    resume_process, etc. through the `broadcast_func` param.
    """
    if not info.context.broadcast_thread:
        return None

    broadcast_queue: queue.Queue = info.context.broadcast_thread.queue

    def _queue_put(process_id: UUID, data: dict) -> None:
        broadcast_queue.put((str(process_id), data))

    return _queue_put

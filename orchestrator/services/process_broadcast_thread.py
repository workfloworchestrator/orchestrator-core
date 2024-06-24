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
from functools import partial
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import Request

from orchestrator.types import BroadcastFunc
from orchestrator.websocket import (
    WS_CHANNELS,
    broadcast_process_update_to_websocket,
    broadcast_process_update_to_websocket_async,
    websocket_manager,
)
from orchestrator.websocket.websocket_manager import WebSocketManager

if TYPE_CHECKING:
    from orchestrator.graphql.types import OrchestratorInfo

BroadcastQueue = queue.Queue[UUID]

logger = structlog.get_logger(__name__)


class ProcessDataBroadcastThread(threading.Thread):
    def __init__(self, _websocket_manager: WebSocketManager, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        self.shutdown = False
        self.queue: BroadcastQueue = queue.Queue()
        self.websocket_manager = _websocket_manager

    def run(self) -> None:
        logger.info("Starting ProcessDataBroadcastThread")
        try:
            loop = asyncio.new_event_loop()  # Create an eventloop specifically for this thread

            while not self.shutdown:
                try:
                    process_id = self.queue.get(block=True, timeout=1)
                except queue.Empty:
                    continue
                logger.debug(
                    "Threadsafe broadcast process update through websocket manager",
                    process_id=process_id,
                    where="ProcessDataBroadcastThread",
                    channels=WS_CHANNELS.EVENTS,
                )
                loop.run_until_complete(broadcast_process_update_to_websocket_async(process_id))

            loop.close()
            logger.info("Shutdown ProcessDataBroadcastThread")
        except Exception:
            logger.exception("Unhandled exception in ProcessDataBroadcastThread, exiting")

    def stop(self) -> None:
        logger.debug("Sending shutdown signal to ProcessDataBroadcastThread")
        self.shutdown = True
        self.join(timeout=5)
        self.is_alive()


def _nop(_process_id: UUID) -> None:
    pass


def _broadcast_ws_fn(process_id: UUID) -> None:
    # Catch all exceptions as broadcasting failure is noncritical to workflow completion
    try:
        broadcast_process_update_to_websocket(process_id)
    except Exception:
        logger.exception("Failed to send process data to websocket")


def _broadcast_queue_put_fn(broadcast_queue: BroadcastQueue, process_id: UUID) -> None:
    # Catch all exceptions as broadcasting failure is noncritical to workflow completion
    try:
        broadcast_queue.put(process_id)
    except Exception:
        logger.exception("An error occurred when putting process_id on broadcast queue")


def api_broadcast_process_data(request: Request) -> BroadcastFunc:
    """Given a FastAPI request, creates a threadsafe callable for broadcasting process data.

    The callable should be created in API endpoints and provided to start_process,
    resume_process, etc. through the `broadcast_func` param.
    """
    if request.app.broadcast_thread:
        return partial(_broadcast_queue_put_fn, request.app.broadcast_thread.queue)

    if websocket_manager.enabled:
        return _broadcast_ws_fn

    logger.debug("WebSocketManager is not enabled. Using no-op broadcasting fn")
    return _nop


def graphql_broadcast_process_data(info: "OrchestratorInfo") -> BroadcastFunc:
    """Given a OrchestratorInfo, creates a threadsafe callable for broadcasting process data.

    The callable should be created in Graphql resolvers and provided to start_process,
    resume_process, etc. through the `broadcast_func` param.
    """
    if info.context.broadcast_thread:
        broadcast_queue: BroadcastQueue = info.context.broadcast_thread.queue
        return partial(_broadcast_queue_put_fn, broadcast_queue)

    if websocket_manager.enabled:
        return _broadcast_ws_fn

    logger.debug("WebSocketManager is not enabled. Using no-op broadcasting fn")
    return _nop

# Copyright 2019-2026 SURF, GÉANT.
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

from orchestrator.core.types import BroadcastFunc
from orchestrator.core.websocket import (
    WS_CHANNELS,
    broadcast_process_update_to_websocket,
    broadcast_process_update_to_websocket_async,
    invalidate_subscription_cache,
    sync_invalidate_subscription_cache,
    websocket_manager,
)
from orchestrator.core.websocket.websocket_manager import WebSocketManager
from orchestrator.core.workflow import UPDATE_SUB_STATUSES

if TYPE_CHECKING:
    from orchestrator.core.db.models import ProcessTable
    from orchestrator.core.graphql.types import OrchestratorInfo

# (process_id, subscription ids whose caches must be invalidated)
BroadcastQueueItem = tuple[UUID, list[UUID]]
BroadcastQueue = queue.Queue[BroadcastQueueItem]

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
                    item = self.queue.get(block=True, timeout=1)
                except queue.Empty:
                    continue
                logger.debug(
                    "Threadsafe broadcast process update through websocket manager",
                    item=item,
                    where="ProcessDataBroadcastThread",
                    channels=WS_CHANNELS.EVENTS,
                )
                # Guard per-item so a single malformed item or failed broadcast doesn't kill the thread
                try:
                    process_id, subscription_ids = item
                    loop.run_until_complete(broadcast_process_update_to_websocket_async(process_id))
                    for subscription_id in subscription_ids:
                        loop.run_until_complete(invalidate_subscription_cache(subscription_id))
                except Exception:
                    logger.exception("Failed to broadcast process update", item=item)

            loop.close()
            logger.info("Shutdown ProcessDataBroadcastThread")
        except Exception:
            logger.exception("Unhandled exception in ProcessDataBroadcastThread, exiting")

    def stop(self) -> None:
        logger.debug("Sending shutdown signal to ProcessDataBroadcastThread")
        self.shutdown = True
        self.join(timeout=5)
        self.is_alive()


def _nop(_process: "ProcessTable") -> None:
    pass


def _broadcast_ws_fn(process: "ProcessTable") -> None:
    # Catch all exceptions as broadcasting failure is noncritical to workflow completion
    try:
        broadcast_process_update_to_websocket(process.process_id)
    except Exception:
        logger.exception("Failed to send process data to websocket")


def _subscription_ids_to_invalidate(process: "ProcessTable") -> list[UUID]:
    """For `UPDATE_SUB_STATUSES`, the related subscription caches must be invalidated so the UI reflects the final state."""
    if process.last_status in UPDATE_SUB_STATUSES:
        return [ps.subscription_id for ps in process.process_subscriptions]
    return []


def _broadcast_queue_put_fn(broadcast_queue: BroadcastQueue, process: "ProcessTable") -> None:
    # Catch all exceptions as broadcasting failure is noncritical to workflow completion
    try:
        broadcast_queue.put((process.process_id, _subscription_ids_to_invalidate(process)))
    except Exception:
        logger.exception("An error occurred when putting process_id on broadcast queue")


def _invalidate_subscription_caches_fn(process: "ProcessTable") -> None:
    """For `UPDATE_SUB_STATUSES`, invalidate the related subscription caches so the UI reflects the final state."""
    # Catch all exceptions as cache invalidation failure is noncritical to workflow completion
    try:
        for subscription_id in _subscription_ids_to_invalidate(process):
            sync_invalidate_subscription_cache(subscription_id)
    except Exception:
        logger.exception("Failed to invalidate subscription caches")


def _with_invalidate_subscription_caches(broadcast_fn: BroadcastFunc) -> BroadcastFunc:
    """Compose a broadcast callable with subscription cache invalidation."""

    def _broadcast_and_invalidate(process: "ProcessTable") -> None:
        broadcast_fn(process)
        _invalidate_subscription_caches_fn(process)

    return _broadcast_and_invalidate


def process_broadcast_fn(process: "ProcessTable") -> None:
    """Default Celery-worker broadcast callback.

    Broadcasts the process update and, for `UPDATE_SUB_STATUSES`, invalidates the related
    subscription caches so the UI reflects the final state.
    """
    _broadcast_ws_fn(process)
    _invalidate_subscription_caches_fn(process)


def api_broadcast_process_data(request: Request) -> BroadcastFunc:
    """Given a FastAPI request, creates a threadsafe callable for broadcasting process data.

    The callable should be created in API endpoints and provided to start_process,
    resume_process, etc. through the `broadcast_func` param.
    """
    if request.app.broadcast_thread:
        # Subscription cache invalidation travels with the queue item and is broadcast by the thread
        return partial(_broadcast_queue_put_fn, request.app.broadcast_thread.queue)

    if websocket_manager.enabled:
        return _with_invalidate_subscription_caches(_broadcast_ws_fn)

    logger.debug("WebSocketManager is not enabled. Using no-op broadcasting fn")
    return _nop


def graphql_broadcast_process_data(info: "OrchestratorInfo") -> BroadcastFunc:
    """Given a OrchestratorInfo, creates a threadsafe callable for broadcasting process data.

    The callable should be created in Graphql resolvers and provided to start_process,
    resume_process, etc. through the `broadcast_func` param.
    """
    if info.context.broadcast_thread:
        # Subscription cache invalidation travels with the queue item and is broadcast by the thread
        broadcast_queue: BroadcastQueue = info.context.broadcast_thread.queue
        return partial(_broadcast_queue_put_fn, broadcast_queue)

    if websocket_manager.enabled:
        return _with_invalidate_subscription_caches(_broadcast_ws_fn)

    logger.debug("WebSocketManager is not enabled. Using no-op broadcasting fn")
    return _nop

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

import threading
from collections import deque
from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

BroadcastCall = Callable[..., None]
BroadcastTask = tuple[BroadcastCall, tuple[Any, ...]]


class WebSocketBroadcastRelay(threading.Thread):
    """Run websocket broadcasts on a dedicated thread, so a slow broadcast server cannot block the caller.

    Callers hand a broadcast function to `submit`, which only appends it to a bounded `deque`. The worker thread
    calls the functions one at a time, in submission order. A broadcast that hangs therefore never stalls the thread
    the caller runs on.

    The deque has a maximum length, so appending to a full queue drops the oldest broadcast. Broadcasts are
    best-effort notifications, so it is better to lose an event than to grow without bound while the broadcast
    server is unavailable.
    """

    JOIN_TIMEOUT = 5

    def __init__(self, maxsize: int = 1000) -> None:
        super().__init__(name="websocket-broadcast-relay", daemon=True)
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")

        self._tasks: deque[BroadcastTask] = deque(maxlen=maxsize)
        self._condition = threading.Condition()
        self._shutdown = False
        self.dropped = 0

    def submit(self, broadcast: BroadcastCall, *args: Any) -> None:
        """Queue a broadcast without waiting for it.

        When the queue is full, the oldest queued broadcast is dropped and counted.

        Args:
            broadcast: Function that performs the broadcast.
            *args: Arguments to call `broadcast` with on the worker thread.
        """
        with self._condition:
            if len(self._tasks) == self._tasks.maxlen:
                self.dropped += 1
                logger.warning(
                    "WebSocket broadcast queue is full, dropping the oldest broadcast",
                    dropped=self.dropped,
                    maxsize=self._tasks.maxlen,
                )

            self._tasks.append((broadcast, args))
            self._condition.notify()

    def run(self) -> None:
        logger.info("Starting websocket broadcast relay")
        while True:
            with self._condition:
                while not self._tasks and not self._shutdown:
                    self._condition.wait()
                if self._shutdown:
                    break

                broadcast, args = self._tasks.popleft()

            try:
                broadcast(*args)
            except Exception:
                logger.exception("Failed to broadcast websocket event")

        logger.info("Shutdown websocket broadcast relay", dropped=self.dropped)

    def stop(self) -> None:
        """Ask the worker to stop and wait for it, unless it is stuck in a broadcast."""
        with self._condition:
            self._shutdown = True
            self._condition.notify()

        self.join(timeout=self.JOIN_TIMEOUT)
        if self.is_alive():
            logger.warning("Websocket broadcast relay did not stop in time", dropped=self.dropped)

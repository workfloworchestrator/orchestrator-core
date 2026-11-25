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

"""Tests for the websocket broadcast relay: non-blocking submission, ordering, drop-oldest and failure isolation."""

import threading
import time

from orchestrator.core.websocket.broadcast_relay import WebSocketBroadcastRelay

WAIT = 3


def test_submit_runs_the_broadcast_on_the_relay_thread():
    broadcasts: list[tuple[str, str]] = []
    done = threading.Event()

    def broadcast(value: str) -> None:
        broadcasts.append((value, threading.current_thread().name))
        done.set()

    relay = WebSocketBroadcastRelay()
    relay.start()
    try:
        relay.submit(broadcast, "schedule-1")
        assert done.wait(timeout=WAIT)
    finally:
        relay.stop()

    ((value, thread_name),) = broadcasts
    assert value == "schedule-1"
    assert thread_name != threading.current_thread().name


def test_submit_does_not_wait_for_a_running_broadcast():
    """A broadcast that never answers the server blocks the relay, not the thread that submits the next one."""
    started = threading.Event()
    release = threading.Event()

    def slow_broadcast() -> None:
        started.set()
        # Block the worker thread to model a broadcast server that does not respond.
        release.wait(timeout=WAIT)

    relay = WebSocketBroadcastRelay()
    relay.start()
    try:
        relay.submit(slow_broadcast)
        assert started.wait(timeout=WAIT)

        submitted_at = time.monotonic()
        relay.submit(slow_broadcast)

        assert time.monotonic() - submitted_at < 0.5
        assert len(relay._tasks) == 1
    finally:
        release.set()
        relay.stop()


def test_submit_drops_the_oldest_broadcast_when_the_queue_is_full():
    def broadcast(value: str) -> None:
        pass

    relay = WebSocketBroadcastRelay(maxsize=2)
    relay.submit(broadcast, "first")
    relay.submit(broadcast, "second")
    relay.submit(broadcast, "third")

    assert [args for _, args in relay._tasks] == [("second",), ("third",)]
    assert relay.dropped == 1


def test_a_failing_broadcast_does_not_stop_the_relay():
    received: list[str] = []
    done = threading.Event()

    def failing_broadcast() -> None:
        raise RuntimeError("broadcast server unavailable")

    def succeeding_broadcast(value: str) -> None:
        received.append(value)
        done.set()

    relay = WebSocketBroadcastRelay()
    relay.start()
    try:
        relay.submit(failing_broadcast)
        relay.submit(succeeding_broadcast, "schedule-1")
        assert done.wait(timeout=WAIT)
    finally:
        relay.stop()

    assert received == ["schedule-1"]


def test_stop_stops_the_worker():
    relay = WebSocketBroadcastRelay()

    relay.start()
    relay.stop()

    assert not relay.is_alive()

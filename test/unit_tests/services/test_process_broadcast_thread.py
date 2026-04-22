"""Tests for ProcessDataBroadcastThread: dispatch selection (queue/ws/nop), exception swallowing, and thread lifecycle."""

import queue
import time
from functools import partial
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.core.services.process_broadcast_thread import (
    ProcessDataBroadcastThread,
    _broadcast_queue_put_fn,
    _broadcast_ws_fn,
    _nop,
    api_broadcast_process_data,
)
from orchestrator.core.websocket.websocket_manager import WebSocketManager

# ---------------------------------------------------------------------------
# _nop
# ---------------------------------------------------------------------------


def test_nop_returns_none():
    process_id = uuid4()
    result = _nop(process_id)
    assert result is None


def test_nop_accepts_any_uuid():
    for _ in range(5):
        _nop(uuid4())  # must not raise


# ---------------------------------------------------------------------------
# _broadcast_ws_fn
# ---------------------------------------------------------------------------


def test_broadcast_ws_fn_calls_broadcast_process_update():
    process_id = uuid4()
    with patch("orchestrator.core.services.process_broadcast_thread.broadcast_process_update_to_websocket") as mock_fn:
        _broadcast_ws_fn(process_id)
    mock_fn.assert_called_once_with(process_id)


def test_broadcast_ws_fn_swallows_exceptions():
    process_id = uuid4()
    with patch(
        "orchestrator.core.services.process_broadcast_thread.broadcast_process_update_to_websocket",
        side_effect=RuntimeError("ws failure"),
    ):
        # Must not raise
        _broadcast_ws_fn(process_id)


# ---------------------------------------------------------------------------
# _broadcast_queue_put_fn
# ---------------------------------------------------------------------------


def test_broadcast_queue_put_fn_puts_process_id_on_queue():
    process_id = uuid4()
    broadcast_queue: queue.Queue = queue.Queue()

    _broadcast_queue_put_fn(broadcast_queue, process_id)

    assert not broadcast_queue.empty()
    assert broadcast_queue.get_nowait() == process_id


def test_broadcast_queue_put_fn_swallows_exceptions():
    process_id = uuid4()
    bad_queue = MagicMock()
    bad_queue.put.side_effect = RuntimeError("queue full")

    # Must not raise
    _broadcast_queue_put_fn(bad_queue, process_id)


# ---------------------------------------------------------------------------
# api_broadcast_process_data
# ---------------------------------------------------------------------------


def test_api_broadcast_process_data_returns_partial_when_broadcast_thread_present():
    mock_request = MagicMock()
    mock_queue: queue.Queue = queue.Queue()
    mock_request.app.broadcast_thread = MagicMock()
    mock_request.app.broadcast_thread.queue = mock_queue

    result = api_broadcast_process_data(mock_request)

    assert isinstance(result, partial)

    # Verify it's bound to the right queue by calling it
    process_id = uuid4()
    result(process_id)
    assert mock_queue.get_nowait() == process_id


def test_api_broadcast_process_data_returns_ws_fn_when_no_thread_but_ws_enabled():
    mock_request = MagicMock()
    mock_request.app.broadcast_thread = None

    with patch("orchestrator.core.services.process_broadcast_thread.websocket_manager") as mock_ws_manager:
        mock_ws_manager.enabled = True
        result = api_broadcast_process_data(mock_request)

    assert result is _broadcast_ws_fn


def test_api_broadcast_process_data_returns_nop_when_no_thread_and_ws_disabled():
    mock_request = MagicMock()
    mock_request.app.broadcast_thread = None

    with patch("orchestrator.core.services.process_broadcast_thread.websocket_manager") as mock_ws_manager:
        mock_ws_manager.enabled = False
        result = api_broadcast_process_data(mock_request)

    assert result is _nop


# ---------------------------------------------------------------------------
# ProcessDataBroadcastThread
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ws_manager():
    return MagicMock(spec=WebSocketManager)


def test_process_data_broadcast_thread_initial_state(mock_ws_manager):
    thread = ProcessDataBroadcastThread(mock_ws_manager, daemon=True)

    assert thread.shutdown is False
    assert isinstance(thread.queue, queue.Queue)
    assert thread.websocket_manager is mock_ws_manager


def test_process_data_broadcast_thread_stop_sets_shutdown(mock_ws_manager):
    thread = ProcessDataBroadcastThread(mock_ws_manager, daemon=True)
    thread.start()

    thread.stop()

    assert thread.shutdown is True


def test_process_data_broadcast_thread_stop_joins_thread(mock_ws_manager):
    thread = ProcessDataBroadcastThread(mock_ws_manager, daemon=True)
    thread.start()
    assert thread.is_alive()

    thread.stop()

    # After stop+join the thread should no longer be alive (it exits its run loop)
    # Give a small grace period for OS scheduling
    deadline = time.time() + 2.0
    while thread.is_alive() and time.time() < deadline:
        time.sleep(0.05)

    assert not thread.is_alive()


def test_process_data_broadcast_thread_processes_queue_item(mock_ws_manager):
    process_id = uuid4()

    async def _noop_coroutine():
        return None

    with patch(
        "orchestrator.core.services.process_broadcast_thread.broadcast_process_update_to_websocket_async",
        side_effect=lambda _pid: _noop_coroutine(),
    ) as mock_async_broadcast:
        thread = ProcessDataBroadcastThread(mock_ws_manager, daemon=True)
        thread.start()

        thread.queue.put(process_id)
        # Give the thread time to process the item
        time.sleep(0.2)

        thread.stop()

    mock_async_broadcast.assert_called_with(process_id)


def test_process_data_broadcast_thread_queue_is_isolated_between_instances(mock_ws_manager):
    thread_a = ProcessDataBroadcastThread(mock_ws_manager, daemon=True)
    thread_b = ProcessDataBroadcastThread(mock_ws_manager, daemon=True)

    assert thread_a.queue is not thread_b.queue

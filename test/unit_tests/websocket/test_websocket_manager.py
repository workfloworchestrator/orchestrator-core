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

"""Tests for WebSocketManager: authorization, Memory/Broadcast backend connect/disconnect, data broadcasting, and channel cleanup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, status
from fastapi.exceptions import HTTPException
from starlette.websockets import WebSocketDisconnect, WebSocketState

from orchestrator.core.websocket.managers.broadcast_websocket_manager import BroadcastWebsocketManager
from orchestrator.core.websocket.managers.memory_websocket_manager import MemoryWebsocketManager
from orchestrator.core.websocket.websocket_manager import WebSocketManager

REDIS_URL = "redis://localhost:6379"
MEMORY_URL = "memory://"


def _make_mock_ws(client_state=WebSocketState.CONNECTED):
    ws = AsyncMock(spec=WebSocket)
    ws.client_state = client_state
    return ws


def _make_broadcast_ws(client_state=WebSocketState.CONNECTED):
    ws = _make_mock_ws(client_state)
    ws.client = ("127.0.0.1", 1234)
    ws.headers = {}
    return ws


# --- Shared fixtures ---


@pytest.fixture
def memory_mgr():
    return MemoryWebsocketManager()


@pytest.fixture
def broadcast_mgr():
    return BroadcastWebsocketManager(REDIS_URL)


@pytest.fixture
def wsm():
    return WebSocketManager(True, MEMORY_URL)


# --- WebSocketManager init ---


@pytest.mark.parametrize(
    "url,expected_type",
    [
        pytest.param("redis://localhost:6379", BroadcastWebsocketManager, id="redis"),
        pytest.param("rediss://localhost:6379", BroadcastWebsocketManager, id="rediss"),
        pytest.param(MEMORY_URL, MemoryWebsocketManager, id="memory"),
    ],
)
def test_websocket_manager_backend_selection(url: str, expected_type: type):
    mgr = WebSocketManager(True, url)
    assert isinstance(mgr._backend, expected_type)


# --- WebSocketManager authorize ---


@pytest.mark.asyncio
@patch("orchestrator.core.websocket.websocket_manager.authorize_websocket", new_callable=AsyncMock)
@patch("orchestrator.core.websocket.websocket_manager.authenticate_websocket", new_callable=AsyncMock)
async def test_authorize_success_returns_none(mock_authn, mock_authz, wsm):
    mock_authn.return_value = {"user": "test"}
    mock_ws = AsyncMock(spec=WebSocket)
    result = await wsm.authorize(mock_ws, "token123")
    assert result is None
    mock_authn.assert_awaited_once_with(websocket=mock_ws, token="token123")  # noqa: S106
    mock_authz.assert_awaited_once_with(mock_ws, {"user": "test"})


@pytest.mark.asyncio
@patch("orchestrator.core.websocket.websocket_manager.authenticate_websocket", new_callable=AsyncMock)
async def test_authorize_http_exception_returns_error(mock_authn, wsm):
    exc = HTTPException(status_code=403, detail="Forbidden")
    mock_authn.side_effect = exc
    mock_ws = AsyncMock(spec=WebSocket)
    result = await wsm.authorize(mock_ws, "bad_token")
    assert result == {"error": vars(exc)}


@pytest.mark.asyncio
@patch("orchestrator.core.websocket.websocket_manager.authorize_websocket", new_callable=AsyncMock)
@patch("orchestrator.core.websocket.websocket_manager.authenticate_websocket", new_callable=AsyncMock)
async def test_authorize_no_user_returns_none(mock_authn, mock_authz, wsm):
    mock_authn.return_value = None
    mock_ws = AsyncMock(spec=WebSocket)
    result = await wsm.authorize(mock_ws, "token")
    assert result is None
    mock_authz.assert_not_awaited()


# --- WebSocketManager connect/disconnect redis ---


@pytest.mark.parametrize(
    "initially_connected,expect_call",
    [
        pytest.param(False, True, id="not-connected"),
        pytest.param(True, False, id="already-connected"),
    ],
)
@pytest.mark.asyncio
async def test_connect_redis(wsm, initially_connected: bool, expect_call: bool):
    wsm.connected = initially_connected
    wsm._backend.connect_redis = AsyncMock()
    await wsm.connect_redis()
    if expect_call:
        assert wsm.connected is True
        wsm._backend.connect_redis.assert_awaited_once()
    else:
        wsm._backend.connect_redis.assert_not_awaited()


@pytest.mark.parametrize(
    "initially_connected,expect_call",
    [
        pytest.param(True, True, id="connected"),
        pytest.param(False, False, id="not-connected"),
    ],
)
@pytest.mark.asyncio
async def test_disconnect_redis(wsm, initially_connected: bool, expect_call: bool):
    wsm.connected = initially_connected
    wsm._backend.disconnect_redis = AsyncMock()
    await wsm.disconnect_redis()
    if expect_call:
        assert wsm.connected is False
        wsm._backend.disconnect_redis.assert_awaited_once()
    else:
        wsm._backend.disconnect_redis.assert_not_awaited()


# --- MemoryWebsocketManager connect ---


@pytest.mark.asyncio
async def test_memory_connect_creates_channel(memory_mgr):
    ws = _make_mock_ws()
    ws.receive_text.side_effect = WebSocketDisconnect(1000)
    await memory_mgr.connect(ws, "ch1")
    assert "ch1" not in memory_mgr.connections_by_pid


@pytest.mark.asyncio
async def test_memory_connect_appends_to_existing_channel(memory_mgr):
    ws1 = _make_mock_ws()
    ws2 = _make_mock_ws()
    memory_mgr.connections_by_pid["ch1"] = [ws1]
    ws2.receive_text.side_effect = WebSocketDisconnect(1000)
    await memory_mgr.connect(ws2, "ch1")
    assert ws1 in memory_mgr.connections_by_pid["ch1"]


@pytest.mark.asyncio
async def test_memory_connect_ping_pong(memory_mgr):
    ws = _make_mock_ws()
    ws.receive_text.side_effect = ["__ping__", WebSocketDisconnect(1000)]
    await memory_mgr.connect(ws, "ch1")
    ws.send_text.assert_any_await("__pong__")


# --- MemoryWebsocketManager disconnect ---


@pytest.mark.parametrize(
    "reason,expect_send",
    [
        pytest.param({"msg": "bye"}, True, id="with-reason"),
        pytest.param(None, False, id="without-reason"),
    ],
)
@pytest.mark.asyncio
async def test_memory_disconnect(memory_mgr, reason, expect_send: bool):
    ws = _make_mock_ws()
    await memory_mgr.disconnect(ws, reason=reason)
    if expect_send:
        ws.send_text.assert_awaited_once()
    else:
        ws.send_text.assert_not_awaited()
    ws.close.assert_awaited_once_with(code=status.WS_1000_NORMAL_CLOSURE)


@pytest.mark.asyncio
async def test_memory_disconnect_all(memory_mgr):
    ws1 = _make_mock_ws(WebSocketState.DISCONNECTED)
    ws2 = _make_mock_ws(WebSocketState.DISCONNECTED)
    memory_mgr.connections_by_pid = {"ch1": [ws1, ws2]}
    await memory_mgr.disconnect_all()
    assert not any(memory_mgr.connections_by_pid.get("ch1", []))


@pytest.mark.asyncio
async def test_memory_disconnect_all_empty(memory_mgr):
    await memory_mgr.disconnect_all()
    assert memory_mgr.connections_by_pid == {}


# --- MemoryWebsocketManager broadcast_data ---


@pytest.mark.asyncio
async def test_memory_broadcast_to_existing_channel(memory_mgr):
    ws = _make_mock_ws()
    memory_mgr.connections_by_pid = {"ch1": [ws]}
    await memory_mgr.broadcast_data(["ch1"], {"key": "value"})
    ws.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_broadcast_to_nonexistent_channel(memory_mgr):
    await memory_mgr.broadcast_data(["nonexistent"], {"key": "value"})
    assert memory_mgr.connections_by_pid == {}


@pytest.mark.asyncio
async def test_memory_broadcast_with_close_flag(memory_mgr):
    ws = _make_mock_ws()
    memory_mgr.connections_by_pid = {"ch1": [ws]}
    await memory_mgr.broadcast_data(["ch1"], {"close": True})
    ws.close.assert_awaited()


@pytest.mark.parametrize("exc_type", [pytest.param(RuntimeError, id="runtime"), pytest.param(ValueError, id="value")])
@pytest.mark.asyncio
async def test_memory_broadcast_error_suppressed(memory_mgr, exc_type):
    ws = _make_mock_ws()
    ws.send_text.side_effect = exc_type("error")
    memory_mgr.connections_by_pid = {"ch1": [ws]}
    await memory_mgr.broadcast_data(["ch1"], {"key": "value"})


# --- MemoryWebsocketManager remove_ws ---


@pytest.mark.asyncio
async def test_memory_remove_connected_ws_calls_disconnect(memory_mgr):
    ws = _make_mock_ws(WebSocketState.CONNECTED)
    memory_mgr.connections_by_pid = {"ch1": [ws]}
    await memory_mgr.remove_ws(ws, "ch1")
    ws.close.assert_awaited()
    assert "ch1" not in memory_mgr.connections_by_pid


@pytest.mark.asyncio
async def test_memory_remove_disconnected_ws_skips_disconnect(memory_mgr):
    ws = _make_mock_ws(WebSocketState.DISCONNECTED)
    memory_mgr.connections_by_pid = {"ch1": [ws]}
    await memory_mgr.remove_ws(ws, "ch1")
    ws.close.assert_not_awaited()
    assert "ch1" not in memory_mgr.connections_by_pid


@pytest.mark.asyncio
async def test_memory_remove_ws_keeps_nonempty_channel(memory_mgr):
    ws1 = _make_mock_ws(WebSocketState.DISCONNECTED)
    ws2 = _make_mock_ws()
    memory_mgr.connections_by_pid = {"ch1": [ws1, ws2]}
    await memory_mgr.remove_ws(ws1, "ch1")
    assert "ch1" in memory_mgr.connections_by_pid
    assert ws2 in memory_mgr.connections_by_pid["ch1"]


@pytest.mark.asyncio
async def test_memory_remove_ws_not_in_channel(memory_mgr):
    ws = _make_mock_ws(WebSocketState.DISCONNECTED)
    memory_mgr.connections_by_pid = {"ch1": []}
    await memory_mgr.remove_ws(ws, "ch1")
    assert memory_mgr.connections_by_pid == {"ch1": []}


# --- MemoryWebsocketManager redis no-ops ---


@pytest.mark.asyncio
async def test_memory_connect_redis_noop(memory_mgr):
    await memory_mgr.connect_redis()
    assert memory_mgr.connections_by_pid == {}


@pytest.mark.asyncio
async def test_memory_disconnect_redis_noop(memory_mgr):
    await memory_mgr.disconnect_redis()
    assert memory_mgr.connections_by_pid == {}


# --- BroadcastWebsocketManager connect ---


@pytest.mark.asyncio
@patch(
    "orchestrator.core.websocket.managers.broadcast_websocket_manager.run_until_first_complete", new_callable=AsyncMock
)
async def test_broadcast_connect_normal(mock_run, broadcast_mgr):
    ws = _make_broadcast_ws()
    await broadcast_mgr.connect(ws, "ch1")
    mock_run.assert_awaited_once()
    assert ws not in broadcast_mgr.connected


@pytest.mark.asyncio
@patch(
    "orchestrator.core.websocket.managers.broadcast_websocket_manager.run_until_first_complete", new_callable=AsyncMock
)
async def test_broadcast_connect_exception_cleanup(mock_run, broadcast_mgr):
    ws = _make_broadcast_ws()
    mock_run.side_effect = RuntimeError("boom")
    await broadcast_mgr.connect(ws, "ch1")
    assert ws not in broadcast_mgr.connected


# --- BroadcastWebsocketManager disconnect ---


@pytest.mark.parametrize(
    "reason,expect_send",
    [
        pytest.param({"msg": "bye"}, True, id="with-reason"),
        pytest.param(None, False, id="without-reason"),
    ],
)
@pytest.mark.asyncio
async def test_broadcast_disconnect(broadcast_mgr, reason, expect_send: bool):
    ws = _make_broadcast_ws()
    broadcast_mgr.connected = [ws]
    await broadcast_mgr.disconnect(ws, reason=reason)
    if expect_send:
        ws.send_text.assert_awaited_once()
    else:
        ws.send_text.assert_not_awaited()
    ws.close.assert_awaited_once()
    assert ws not in broadcast_mgr.connected


@pytest.mark.asyncio
async def test_broadcast_disconnect_all(broadcast_mgr):
    ws = _make_broadcast_ws()
    broadcast_mgr.connected = [ws]
    await broadcast_mgr.disconnect_all()
    ws.close.assert_awaited()
    ws.send_text.assert_awaited()


# --- BroadcastWebsocketManager receiver ---


@pytest.mark.asyncio
async def test_broadcast_receiver_ping_pong(broadcast_mgr):
    ws = _make_broadcast_ws()
    ws.receive_text.side_effect = ["__ping__", WebSocketDisconnect(1000)]
    await broadcast_mgr.receiver(ws, "ch1")
    ws.send_text.assert_awaited_once_with("__pong__")


@pytest.mark.asyncio
async def test_broadcast_receiver_disconnect_breaks(broadcast_mgr):
    ws = _make_broadcast_ws()
    ws.receive_text.side_effect = WebSocketDisconnect(1000)
    await broadcast_mgr.receiver(ws, "ch1")


@pytest.mark.asyncio
async def test_broadcast_receiver_exception_breaks(broadcast_mgr):
    ws = _make_broadcast_ws()
    ws.receive_text.side_effect = RuntimeError("connection lost")
    await broadcast_mgr.receiver(ws, "ch1")


@pytest.mark.asyncio
async def test_broadcast_receiver_normal_message_no_pong(broadcast_mgr):
    ws = _make_broadcast_ws()
    ws.receive_text.side_effect = ["hello", WebSocketDisconnect(1000)]
    await broadcast_mgr.receiver(ws, "ch1")
    ws.send_text.assert_not_awaited()


# --- BroadcastWebsocketManager sender ---


def _mock_subscriber(messages):
    """Create a mock subscriber context manager that yields messages then raises."""
    subscriber = AsyncMock()
    subscriber.get_message = AsyncMock(side_effect=messages)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=subscriber)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_broadcast_sender_valid_message(broadcast_mgr):
    ws = _make_broadcast_ws()
    messages = [{"type": "message", "data": b"hello"}, Exception("stop")]
    broadcast_mgr.broadcast = MagicMock()
    broadcast_mgr.broadcast.subscriber = MagicMock(return_value=_mock_subscriber(messages))
    await broadcast_mgr.sender(ws, "ch1")
    ws.send_text.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_broadcast_sender_none_message_skipped(broadcast_mgr):
    ws = _make_broadcast_ws()
    messages = [None, {"type": "message", "data": b"after_none"}, Exception("stop")]
    broadcast_mgr.broadcast = MagicMock()
    broadcast_mgr.broadcast.subscriber = MagicMock(return_value=_mock_subscriber(messages))
    await broadcast_mgr.sender(ws, "ch1")
    ws.send_text.assert_awaited_once_with("after_none")


@pytest.mark.asyncio
async def test_broadcast_sender_unrecognized_message_dropped(broadcast_mgr):
    ws = _make_broadcast_ws()
    messages = [{"type": "unknown", "data": "stuff"}, Exception("stop")]
    broadcast_mgr.broadcast = MagicMock()
    broadcast_mgr.broadcast.subscriber = MagicMock(return_value=_mock_subscriber(messages))
    await broadcast_mgr.sender(ws, "ch1")
    ws.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_sender_exception_logged(broadcast_mgr):
    ws = _make_broadcast_ws()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("redis down"))
    ctx.__aexit__ = AsyncMock(return_value=False)
    broadcast_mgr.broadcast = MagicMock()
    broadcast_mgr.broadcast.subscriber = MagicMock(return_value=ctx)
    await broadcast_mgr.sender(ws, "ch1")


# --- BroadcastWebsocketManager broadcast_data ---


@pytest.mark.asyncio
async def test_broadcast_publishes_to_all_channels():
    mgr = BroadcastWebsocketManager(REDIS_URL)
    mock_pipe = AsyncMock()
    mock_pipe.publish = MagicMock()

    mock_pipeline_ctx = AsyncMock()
    mock_pipeline_ctx.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipeline_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("orchestrator.core.websocket.managers.broadcast_websocket_manager.RedisBroadcast") as MockBroadcast:
        mock_instance = MagicMock()
        mock_instance.pipeline = MagicMock(return_value=mock_pipeline_ctx)
        MockBroadcast.return_value = mock_instance

        await mgr.broadcast_data(["ch1", "ch2"], {"key": "value"})
        assert mock_pipe.publish.call_count == 2


# --- BroadcastWebsocketManager remove_ws ---


@pytest.mark.parametrize(
    "in_list",
    [
        pytest.param(True, id="in-list"),
        pytest.param(False, id="not-in-list"),
    ],
)
def test_broadcast_remove_ws(broadcast_mgr, in_list: bool):
    ws = _make_broadcast_ws()
    broadcast_mgr.connected = [ws] if in_list else []
    broadcast_mgr.remove_ws_from_connected_list(ws)
    assert ws not in broadcast_mgr.connected

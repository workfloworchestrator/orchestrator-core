from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, status
from fastapi.exceptions import HTTPException
from starlette.websockets import WebSocketDisconnect, WebSocketState

from orchestrator.websocket.managers.broadcast_websocket_manager import BroadcastWebsocketManager
from orchestrator.websocket.managers.memory_websocket_manager import MemoryWebsocketManager
from orchestrator.websocket.websocket_manager import WebSocketManager

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


# --- WebSocketManager ---


class TestWebSocketManagerInit:
    @pytest.mark.parametrize("url", ["redis://localhost:6379", "rediss://localhost:6379"])
    def test_redis_schemes_use_broadcast_backend(self, url):
        wsm = WebSocketManager(True, url)
        assert isinstance(wsm._backend, BroadcastWebsocketManager)

    def test_memory_scheme_uses_memory_backend(self):
        wsm = WebSocketManager(True, MEMORY_URL)
        assert isinstance(wsm._backend, MemoryWebsocketManager)


class TestWebSocketManagerAuthorize:
    @pytest.fixture
    def mock_ws(self):
        return AsyncMock(spec=WebSocket)

    @pytest.mark.asyncio
    @patch("orchestrator.websocket.websocket_manager.authorize_websocket", new_callable=AsyncMock)
    @patch("orchestrator.websocket.websocket_manager.authenticate_websocket", new_callable=AsyncMock)
    async def test_authorize_success_returns_none(self, mock_authn, mock_authz, wsm, mock_ws):
        mock_authn.return_value = {"user": "test"}
        result = await wsm.authorize(mock_ws, "token123")
        assert result is None
        mock_authn.assert_awaited_once_with(websocket=mock_ws, token="token123")  # noqa: S106
        mock_authz.assert_awaited_once_with(mock_ws, {"user": "test"})

    @pytest.mark.asyncio
    @patch("orchestrator.websocket.websocket_manager.authenticate_websocket", new_callable=AsyncMock)
    async def test_authorize_http_exception_returns_error(self, mock_authn, wsm, mock_ws):
        exc = HTTPException(status_code=403, detail="Forbidden")
        mock_authn.side_effect = exc
        result = await wsm.authorize(mock_ws, "bad_token")
        assert result == {"error": vars(exc)}

    @pytest.mark.asyncio
    @patch("orchestrator.websocket.websocket_manager.authorize_websocket", new_callable=AsyncMock)
    @patch("orchestrator.websocket.websocket_manager.authenticate_websocket", new_callable=AsyncMock)
    async def test_authorize_no_user_returns_none(self, mock_authn, mock_authz, wsm, mock_ws):
        mock_authn.return_value = None
        result = await wsm.authorize(mock_ws, "token")
        assert result is None
        mock_authz.assert_not_awaited()


class TestWebSocketManagerConnectDisconnectRedis:
    @pytest.mark.asyncio
    async def test_connect_redis_when_not_connected(self, wsm):
        wsm._backend.connect_redis = AsyncMock()
        await wsm.connect_redis()
        assert wsm.connected is True
        wsm._backend.connect_redis.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_redis_idempotent(self, wsm):
        wsm.connected = True
        wsm._backend.connect_redis = AsyncMock()
        await wsm.connect_redis()
        wsm._backend.connect_redis.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_redis_when_connected(self, wsm):
        wsm.connected = True
        wsm._backend.disconnect_redis = AsyncMock()
        await wsm.disconnect_redis()
        assert wsm.connected is False
        wsm._backend.disconnect_redis.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_redis_idempotent(self, wsm):
        wsm.connected = False
        wsm._backend.disconnect_redis = AsyncMock()
        await wsm.disconnect_redis()
        wsm._backend.disconnect_redis.assert_not_awaited()


# --- MemoryWebsocketManager ---


class TestMemoryConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_new_channel(self, memory_mgr):
        ws = _make_mock_ws()
        ws.receive_text.side_effect = WebSocketDisconnect(1000)
        await memory_mgr.connect(ws, "ch1")
        assert "ch1" not in memory_mgr.connections_by_pid

    @pytest.mark.asyncio
    async def test_connect_appends_to_existing_channel(self, memory_mgr):
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        memory_mgr.connections_by_pid["ch1"] = [ws1]
        ws2.receive_text.side_effect = WebSocketDisconnect(1000)
        await memory_mgr.connect(ws2, "ch1")
        assert ws1 in memory_mgr.connections_by_pid["ch1"]

    @pytest.mark.asyncio
    async def test_connect_ping_pong(self, memory_mgr):
        ws = _make_mock_ws()
        ws.receive_text.side_effect = ["__ping__", WebSocketDisconnect(1000)]
        await memory_mgr.connect(ws, "ch1")
        ws.send_text.assert_any_await("__pong__")


class TestMemoryDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_with_reason(self, memory_mgr):
        ws = _make_mock_ws()
        await memory_mgr.disconnect(ws, reason={"msg": "bye"})
        ws.send_text.assert_awaited_once()
        ws.close.assert_awaited_once_with(code=status.WS_1000_NORMAL_CLOSURE)

    @pytest.mark.asyncio
    async def test_disconnect_without_reason(self, memory_mgr):
        ws = _make_mock_ws()
        await memory_mgr.disconnect(ws)
        ws.send_text.assert_not_awaited()
        ws.close.assert_awaited_once_with(code=status.WS_1000_NORMAL_CLOSURE)


class TestMemoryDisconnectAll:
    @pytest.mark.asyncio
    async def test_disconnect_all_removes_all(self, memory_mgr):
        ws1 = _make_mock_ws(WebSocketState.DISCONNECTED)
        ws2 = _make_mock_ws(WebSocketState.DISCONNECTED)
        memory_mgr.connections_by_pid = {"ch1": [ws1, ws2]}
        await memory_mgr.disconnect_all()
        assert not any(memory_mgr.connections_by_pid.get("ch1", []))

    @pytest.mark.asyncio
    async def test_disconnect_all_empty(self, memory_mgr):
        await memory_mgr.disconnect_all()
        assert memory_mgr.connections_by_pid == {}


class TestMemoryBroadcastData:
    @pytest.mark.asyncio
    async def test_broadcast_to_existing_channel(self, memory_mgr):
        ws = _make_mock_ws()
        memory_mgr.connections_by_pid = {"ch1": [ws]}
        await memory_mgr.broadcast_data(["ch1"], {"key": "value"})
        ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_channel(self, memory_mgr):
        await memory_mgr.broadcast_data(["nonexistent"], {"key": "value"})
        assert memory_mgr.connections_by_pid == {}

    @pytest.mark.asyncio
    async def test_broadcast_with_close_flag(self, memory_mgr):
        ws = _make_mock_ws()
        memory_mgr.connections_by_pid = {"ch1": [ws]}
        await memory_mgr.broadcast_data(["ch1"], {"close": True})
        ws.close.assert_awaited()

    @pytest.mark.parametrize("exc_type", [RuntimeError, ValueError])
    @pytest.mark.asyncio
    async def test_broadcast_error_suppressed(self, memory_mgr, exc_type):
        ws = _make_mock_ws()
        ws.send_text.side_effect = exc_type("error")
        memory_mgr.connections_by_pid = {"ch1": [ws]}
        await memory_mgr.broadcast_data(["ch1"], {"key": "value"})


class TestMemoryRemoveWs:
    @pytest.mark.asyncio
    async def test_remove_connected_ws_calls_disconnect(self, memory_mgr):
        ws = _make_mock_ws(WebSocketState.CONNECTED)
        memory_mgr.connections_by_pid = {"ch1": [ws]}
        await memory_mgr.remove_ws(ws, "ch1")
        ws.close.assert_awaited()
        assert "ch1" not in memory_mgr.connections_by_pid

    @pytest.mark.asyncio
    async def test_remove_disconnected_ws_skips_disconnect(self, memory_mgr):
        ws = _make_mock_ws(WebSocketState.DISCONNECTED)
        memory_mgr.connections_by_pid = {"ch1": [ws]}
        await memory_mgr.remove_ws(ws, "ch1")
        ws.close.assert_not_awaited()
        assert "ch1" not in memory_mgr.connections_by_pid

    @pytest.mark.asyncio
    async def test_remove_ws_cleans_empty_channel(self, memory_mgr):
        ws = _make_mock_ws(WebSocketState.DISCONNECTED)
        memory_mgr.connections_by_pid = {"ch1": [ws]}
        await memory_mgr.remove_ws(ws, "ch1")
        assert "ch1" not in memory_mgr.connections_by_pid

    @pytest.mark.asyncio
    async def test_remove_ws_keeps_nonempty_channel(self, memory_mgr):
        ws1 = _make_mock_ws(WebSocketState.DISCONNECTED)
        ws2 = _make_mock_ws()
        memory_mgr.connections_by_pid = {"ch1": [ws1, ws2]}
        await memory_mgr.remove_ws(ws1, "ch1")
        assert "ch1" in memory_mgr.connections_by_pid
        assert ws2 in memory_mgr.connections_by_pid["ch1"]

    @pytest.mark.asyncio
    async def test_remove_ws_not_in_channel(self, memory_mgr):
        ws = _make_mock_ws(WebSocketState.DISCONNECTED)
        memory_mgr.connections_by_pid = {"ch1": []}
        await memory_mgr.remove_ws(ws, "ch1")
        assert memory_mgr.connections_by_pid == {"ch1": []}


class TestMemoryRedisNoOps:
    @pytest.mark.asyncio
    async def test_connect_redis_noop(self, memory_mgr):
        await memory_mgr.connect_redis()
        assert memory_mgr.connections_by_pid == {}

    @pytest.mark.asyncio
    async def test_disconnect_redis_noop(self, memory_mgr):
        await memory_mgr.disconnect_redis()
        assert memory_mgr.connections_by_pid == {}


# --- BroadcastWebsocketManager ---


class TestBroadcastConnect:
    @pytest.mark.asyncio
    @patch(
        "orchestrator.websocket.managers.broadcast_websocket_manager.run_until_first_complete", new_callable=AsyncMock
    )
    async def test_connect_normal_completion(self, mock_run, broadcast_mgr):
        ws = _make_broadcast_ws()
        await broadcast_mgr.connect(ws, "ch1")
        mock_run.assert_awaited_once()
        assert ws not in broadcast_mgr.connected

    @pytest.mark.asyncio
    @patch(
        "orchestrator.websocket.managers.broadcast_websocket_manager.run_until_first_complete", new_callable=AsyncMock
    )
    async def test_connect_exception_logged_and_cleaned_up(self, mock_run, broadcast_mgr):
        ws = _make_broadcast_ws()
        mock_run.side_effect = RuntimeError("boom")
        await broadcast_mgr.connect(ws, "ch1")
        assert ws not in broadcast_mgr.connected


class TestBroadcastDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_with_reason(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        broadcast_mgr.connected = [ws]
        await broadcast_mgr.disconnect(ws, reason={"msg": "bye"})
        ws.send_text.assert_awaited_once()
        ws.close.assert_awaited_once()
        assert ws not in broadcast_mgr.connected

    @pytest.mark.asyncio
    async def test_disconnect_without_reason(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        broadcast_mgr.connected = [ws]
        await broadcast_mgr.disconnect(ws)
        ws.send_text.assert_not_awaited()
        ws.close.assert_awaited_once()
        assert ws not in broadcast_mgr.connected


class TestBroadcastDisconnectAll:
    @pytest.mark.asyncio
    async def test_disconnect_all_single(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        broadcast_mgr.connected = [ws]
        await broadcast_mgr.disconnect_all()
        ws.close.assert_awaited()
        ws.send_text.assert_awaited()


class TestBroadcastReceiver:
    @pytest.mark.asyncio
    async def test_receiver_ping_pong(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        ws.receive_text.side_effect = ["__ping__", WebSocketDisconnect(1000)]
        await broadcast_mgr.receiver(ws, "ch1")
        ws.send_text.assert_awaited_once_with("__pong__")

    @pytest.mark.asyncio
    async def test_receiver_websocket_disconnect_breaks(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        ws.receive_text.side_effect = WebSocketDisconnect(1000)
        await broadcast_mgr.receiver(ws, "ch1")

    @pytest.mark.asyncio
    async def test_receiver_generic_exception_breaks(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        ws.receive_text.side_effect = RuntimeError("connection lost")
        await broadcast_mgr.receiver(ws, "ch1")

    @pytest.mark.asyncio
    async def test_receiver_normal_message_no_pong(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        ws.receive_text.side_effect = ["hello", WebSocketDisconnect(1000)]
        await broadcast_mgr.receiver(ws, "ch1")
        ws.send_text.assert_not_awaited()


def _mock_subscriber(messages):
    """Create a mock subscriber context manager that yields messages then raises."""
    subscriber = AsyncMock()
    subscriber.get_message = AsyncMock(side_effect=messages)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=subscriber)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestBroadcastSender:
    @pytest.mark.asyncio
    async def test_sender_valid_message(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        messages = [{"type": "message", "data": b"hello"}, Exception("stop")]
        broadcast_mgr.broadcast = MagicMock()
        broadcast_mgr.broadcast.subscriber = MagicMock(return_value=_mock_subscriber(messages))
        await broadcast_mgr.sender(ws, "ch1")
        ws.send_text.assert_awaited_once_with("hello")

    @pytest.mark.asyncio
    async def test_sender_none_message_skipped(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        messages = [None, {"type": "message", "data": b"after_none"}, Exception("stop")]
        broadcast_mgr.broadcast = MagicMock()
        broadcast_mgr.broadcast.subscriber = MagicMock(return_value=_mock_subscriber(messages))
        await broadcast_mgr.sender(ws, "ch1")
        ws.send_text.assert_awaited_once_with("after_none")

    @pytest.mark.asyncio
    async def test_sender_unrecognized_message_dropped(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        messages = [{"type": "unknown", "data": "stuff"}, Exception("stop")]
        broadcast_mgr.broadcast = MagicMock()
        broadcast_mgr.broadcast.subscriber = MagicMock(return_value=_mock_subscriber(messages))
        await broadcast_mgr.sender(ws, "ch1")
        ws.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sender_exception_logged(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("redis down"))
        ctx.__aexit__ = AsyncMock(return_value=False)
        broadcast_mgr.broadcast = MagicMock()
        broadcast_mgr.broadcast.subscriber = MagicMock(return_value=ctx)
        await broadcast_mgr.sender(ws, "ch1")


class TestBroadcastBroadcastData:
    @pytest.mark.asyncio
    async def test_publishes_to_all_channels(self):
        mgr = BroadcastWebsocketManager(REDIS_URL)
        mock_pipe = AsyncMock()
        mock_pipe.publish = MagicMock()

        mock_pipeline_ctx = AsyncMock()
        mock_pipeline_ctx.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipeline_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("orchestrator.websocket.managers.broadcast_websocket_manager.RedisBroadcast") as MockBroadcast:
            mock_instance = MagicMock()
            mock_instance.pipeline = MagicMock(return_value=mock_pipeline_ctx)
            MockBroadcast.return_value = mock_instance

            await mgr.broadcast_data(["ch1", "ch2"], {"key": "value"})
            assert mock_pipe.publish.call_count == 2


class TestBroadcastRemoveWs:
    def test_remove_ws_in_list(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        broadcast_mgr.connected = [ws]
        broadcast_mgr.remove_ws_from_connected_list(ws)
        assert ws not in broadcast_mgr.connected

    def test_remove_ws_not_in_list(self, broadcast_mgr):
        ws = _make_broadcast_ws()
        broadcast_mgr.connected = []
        broadcast_mgr.remove_ws_from_connected_list(ws)
        assert broadcast_mgr.connected == []

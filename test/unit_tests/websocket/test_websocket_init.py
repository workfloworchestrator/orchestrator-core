from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
from uuid import uuid4

import pytest

from orchestrator.websocket import (
    WS_CHANNELS,
    WrappedWebSocketManager,
    broadcast_invalidate_cache,
    broadcast_invalidate_status_counts,
    broadcast_invalidate_status_counts_async,
    broadcast_process_update_to_websocket,
    broadcast_process_update_to_websocket_async,
    empty_fn,
    init_websocket_manager,
    invalidate_subscription_cache,
    is_process_active,
    sync_broadcast_invalidate_cache,
    sync_invalidate_subscription_cache,
)
from orchestrator.websocket.websocket_manager import WebSocketManager
from orchestrator.workflow import ProcessStatus


class TestEmptyFn:
    @pytest.mark.asyncio
    async def test_returns_none(self):
        result = await empty_fn()
        assert result is None

    @pytest.mark.asyncio
    async def test_accepts_args_kwargs(self):
        result = await empty_fn(1, 2, key="value")
        assert result is None


class TestWrappedWebSocketManager:
    def test_getattr_no_wrappee_underscore_returns_none(self):
        wrapped = WrappedWebSocketManager(wrappee=None)
        result = wrapped.some_method_with_underscore
        assert result is None

    def test_getattr_no_wrappee_non_underscore_raises(self):
        wrapped = WrappedWebSocketManager(wrappee=None)
        with pytest.raises(RuntimeWarning, match="No WebSocketManager configured"):
            wrapped.enabled  # noqa: B018

    def test_getattr_disabled_returns_empty_fn(self):
        mock_wsm = create_autospec(WebSocketManager, instance=True)
        mock_wsm.enabled = False
        wrapped = WrappedWebSocketManager(wrappee=mock_wsm)
        result = wrapped.broadcast_data
        assert result is empty_fn

    def test_getattr_disabled_enabled_attr_passes_through(self):
        mock_wsm = create_autospec(WebSocketManager, instance=True)
        mock_wsm.enabled = False
        wrapped = WrappedWebSocketManager(wrappee=mock_wsm)
        assert wrapped.enabled is False

    def test_getattr_enabled_delegates(self):
        mock_wsm = create_autospec(WebSocketManager, instance=True)
        mock_wsm.enabled = True
        mock_wsm.some_attr = "delegated_value"
        wrapped = WrappedWebSocketManager(wrappee=mock_wsm)
        assert wrapped.some_attr == "delegated_value"

    def test_update_enabled_logs_info(self):
        wrapped = WrappedWebSocketManager()
        mock_wsm = create_autospec(WebSocketManager, instance=True)
        mock_wsm.enabled = True
        wrapped.update(mock_wsm)
        assert wrapped.wrapped_websocket_manager is mock_wsm

    def test_update_disabled_logs_warning(self):
        wrapped = WrappedWebSocketManager()
        mock_wsm = create_autospec(WebSocketManager, instance=True)
        mock_wsm.enabled = False
        wrapped.update(mock_wsm)
        assert wrapped.wrapped_websocket_manager is mock_wsm


class TestInitWebsocketManager:
    @patch("orchestrator.websocket.WebSocketManager")
    def test_creates_and_updates_wrapped_manager(self, MockWSM):
        mock_instance = MagicMock()
        MockWSM.return_value = mock_instance
        settings = MagicMock()
        settings.ENABLE_WEBSOCKETS = True
        settings.WEBSOCKET_BROADCASTER_URL.get_secret_value.return_value = "memory://"
        result = init_websocket_manager(settings)
        MockWSM.assert_called_once_with(True, "memory://")
        assert result is not None


class TestIsProcessActive:
    @pytest.mark.parametrize(
        "process_status,expected",
        [
            (ProcessStatus.RUNNING, True),
            (ProcessStatus.SUSPENDED, True),
            (ProcessStatus.WAITING, True),
            (ProcessStatus.COMPLETED, False),
            (ProcessStatus.FAILED, False),
            (ProcessStatus.ABORTED, False),
            (ProcessStatus.CREATED, False),
            (ProcessStatus.API_UNAVAILABLE, False),
            (ProcessStatus.INCONSISTENT_DATA, False),
        ],
    )
    def test_is_process_active(self, process_status, expected):
        assert is_process_active({"status": process_status}) is expected


class TestBroadcastHelpers:
    @pytest.mark.asyncio
    async def test_broadcast_event_sends_to_events_channel(self):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.broadcast_data = AsyncMock()
            from orchestrator.websocket import _broadcast_event

            await _broadcast_event("testEvent", {"foo": "bar"})
            mock_wsm.broadcast_data.assert_awaited_once_with(
                [WS_CHANNELS.EVENTS], {"name": "testEvent", "value": {"foo": "bar"}}
            )

    @pytest.mark.asyncio
    async def test_invalidate_subscription_cache_all_true(self):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.broadcast_data = AsyncMock()
            sub_id = uuid4()
            await invalidate_subscription_cache(sub_id, invalidate_all=True)
            assert mock_wsm.broadcast_data.await_count == 3

    @pytest.mark.asyncio
    async def test_invalidate_subscription_cache_all_false(self):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.broadcast_data = AsyncMock()
            sub_id = uuid4()
            await invalidate_subscription_cache(sub_id, invalidate_all=False)
            assert mock_wsm.broadcast_data.await_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_invalidate_status_counts_async_enabled(self):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = True
            mock_wsm.broadcast_data = AsyncMock()
            await broadcast_invalidate_status_counts_async()
            mock_wsm.broadcast_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_invalidate_status_counts_async_disabled(self):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = False
            await broadcast_invalidate_status_counts_async()
            # Should early return, no broadcast_data call

    @patch("orchestrator.websocket.sync_broadcast_invalidate_cache")
    def test_broadcast_invalidate_status_counts_sync_enabled(self, mock_sync):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = True
            broadcast_invalidate_status_counts()
            mock_sync.assert_called_once_with({"type": "processStatusCounts"})

    @patch("orchestrator.websocket.sync_broadcast_invalidate_cache")
    def test_broadcast_invalidate_status_counts_sync_disabled(self, mock_sync):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = False
            broadcast_invalidate_status_counts()
            mock_sync.assert_not_called()

    @patch("orchestrator.websocket.sync_broadcast_invalidate_cache")
    def test_broadcast_process_update_sync_enabled(self, mock_sync):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = True
            pid = uuid4()
            broadcast_process_update_to_websocket(pid)
            assert mock_sync.call_count == 2

    @patch("orchestrator.websocket.sync_broadcast_invalidate_cache")
    def test_broadcast_process_update_sync_disabled(self, mock_sync):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = False
            broadcast_process_update_to_websocket(uuid4())
            mock_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_process_update_async_enabled(self):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = True
            mock_wsm.broadcast_data = AsyncMock()
            pid = uuid4()
            await broadcast_process_update_to_websocket_async(pid)
            assert mock_wsm.broadcast_data.await_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_process_update_async_disabled(self):
        with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
            mock_wsm.enabled = False
            await broadcast_process_update_to_websocket_async(uuid4())


class TestSyncWrappers:
    @patch("orchestrator.websocket.anyio")
    def test_sync_broadcast_invalidate_cache(self, mock_anyio):
        cache_obj = {"type": "test"}
        sync_broadcast_invalidate_cache(cache_obj)
        mock_anyio.run.assert_called_once_with(broadcast_invalidate_cache, cache_obj)

    @patch("orchestrator.websocket.anyio")
    def test_sync_invalidate_subscription_cache(self, mock_anyio):
        sub_id = uuid4()
        sync_invalidate_subscription_cache(sub_id, True)
        mock_anyio.run.assert_called_once_with(invalidate_subscription_cache, sub_id, True)

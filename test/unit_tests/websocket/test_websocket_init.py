"""Tests for websocket module init: WrappedWebSocketManager (enabled/disabled delegation, raising when unconfigured), broadcast helpers, and sync wrappers."""

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

# --- empty_fn ---


@pytest.mark.asyncio
async def test_empty_fn_returns_none():
    assert await empty_fn() is None


@pytest.mark.asyncio
async def test_empty_fn_accepts_args_kwargs():
    assert await empty_fn(1, 2, key="value") is None


# --- WrappedWebSocketManager ---


def test_wrapped_no_wrappee_underscore_returns_empty_fn():
    wrapped = WrappedWebSocketManager(wrappee=None)
    assert wrapped.some_method_with_underscore is empty_fn


def test_wrapped_no_wrappee_enabled_returns_false():
    wrapped = WrappedWebSocketManager(wrappee=None)
    assert wrapped.enabled is False


def test_wrapped_no_wrappee_non_underscore_raises():
    wrapped = WrappedWebSocketManager(wrappee=None)
    with pytest.raises(RuntimeWarning, match="No WebSocketManager configured"):
        wrapped.someprop  # noqa: B018


def test_wrapped_disabled_returns_empty_fn():
    mock_wsm = create_autospec(WebSocketManager, instance=True)
    mock_wsm.enabled = False
    wrapped = WrappedWebSocketManager(wrappee=mock_wsm)
    assert wrapped.broadcast_data is empty_fn


def test_wrapped_disabled_enabled_attr_passes_through():
    mock_wsm = create_autospec(WebSocketManager, instance=True)
    mock_wsm.enabled = False
    wrapped = WrappedWebSocketManager(wrappee=mock_wsm)
    assert wrapped.enabled is False


def test_wrapped_enabled_delegates():
    mock_wsm = create_autospec(WebSocketManager, instance=True)
    mock_wsm.enabled = True
    mock_wsm.some_attr = "delegated_value"
    wrapped = WrappedWebSocketManager(wrappee=mock_wsm)
    assert wrapped.some_attr == "delegated_value"


@pytest.mark.parametrize(
    "enabled",
    [
        pytest.param(True, id="enabled"),
        pytest.param(False, id="disabled"),
    ],
)
def test_wrapped_update_stores_wrappee(enabled: bool):
    wrapped = WrappedWebSocketManager()
    mock_wsm = create_autospec(WebSocketManager, instance=True)
    mock_wsm.enabled = enabled
    wrapped.update(mock_wsm)
    assert wrapped.wrapped_websocket_manager is mock_wsm


# --- init_websocket_manager ---


@patch("orchestrator.websocket.WebSocketManager")
def test_init_websocket_manager_creates_and_updates(MockWSM):
    mock_instance = MagicMock()
    MockWSM.return_value = mock_instance
    settings = MagicMock()
    settings.ENABLE_WEBSOCKETS = True
    settings.WEBSOCKET_BROADCASTER_URL.get_secret_value.return_value = "memory://"
    result = init_websocket_manager(settings)
    MockWSM.assert_called_once_with(True, "memory://")
    assert result is not None


# --- is_process_active ---


@pytest.mark.parametrize(
    "process_status,expected",
    [
        pytest.param(ProcessStatus.RUNNING, True, id="running"),
        pytest.param(ProcessStatus.SUSPENDED, True, id="suspended"),
        pytest.param(ProcessStatus.WAITING, True, id="waiting"),
        pytest.param(ProcessStatus.COMPLETED, False, id="completed"),
        pytest.param(ProcessStatus.FAILED, False, id="failed"),
        pytest.param(ProcessStatus.ABORTED, False, id="aborted"),
        pytest.param(ProcessStatus.CREATED, False, id="created"),
        pytest.param(ProcessStatus.API_UNAVAILABLE, False, id="api-unavailable"),
        pytest.param(ProcessStatus.INCONSISTENT_DATA, False, id="inconsistent-data"),
    ],
)
def test_is_process_active(process_status, expected):
    assert is_process_active({"status": process_status}) is expected


# --- broadcast helpers ---


@pytest.mark.asyncio
async def test_broadcast_event_sends_to_events_channel():
    with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
        mock_wsm.broadcast_data = AsyncMock()
        from orchestrator.websocket import _broadcast_event

        await _broadcast_event("testEvent", {"foo": "bar"})
        mock_wsm.broadcast_data.assert_awaited_once_with(
            [WS_CHANNELS.EVENTS], {"name": "testEvent", "value": {"foo": "bar"}}
        )


@pytest.mark.parametrize(
    "invalidate_all,expected_call_count",
    [
        pytest.param(True, 3, id="all-true"),
        pytest.param(False, 2, id="all-false"),
    ],
)
@pytest.mark.asyncio
async def test_invalidate_subscription_cache(invalidate_all: bool, expected_call_count: int):
    with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
        mock_wsm.broadcast_data = AsyncMock()
        await invalidate_subscription_cache(uuid4(), invalidate_all=invalidate_all)
        assert mock_wsm.broadcast_data.await_count == expected_call_count


@pytest.mark.parametrize(
    "enabled",
    [
        pytest.param(True, id="enabled"),
        pytest.param(False, id="disabled"),
    ],
)
@pytest.mark.asyncio
async def test_broadcast_invalidate_status_counts_async(enabled: bool):
    with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
        mock_wsm.enabled = enabled
        mock_wsm.broadcast_data = AsyncMock()
        await broadcast_invalidate_status_counts_async()
        if enabled:
            mock_wsm.broadcast_data.assert_awaited_once()


@pytest.mark.parametrize(
    "enabled,sync_called",
    [
        pytest.param(True, True, id="enabled"),
        pytest.param(False, False, id="disabled"),
    ],
)
@patch("orchestrator.websocket.sync_broadcast_invalidate_cache")
def test_broadcast_invalidate_status_counts_sync(mock_sync, enabled: bool, sync_called: bool):
    with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
        mock_wsm.enabled = enabled
        broadcast_invalidate_status_counts()
        if sync_called:
            mock_sync.assert_called_once_with({"type": "processStatusCounts"})
        else:
            mock_sync.assert_not_called()


@pytest.mark.parametrize(
    "enabled,expected_call_count",
    [
        pytest.param(True, 2, id="enabled"),
        pytest.param(False, 0, id="disabled"),
    ],
)
@patch("orchestrator.websocket.sync_broadcast_invalidate_cache")
def test_broadcast_process_update_sync(mock_sync, enabled: bool, expected_call_count: int):
    with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
        mock_wsm.enabled = enabled
        broadcast_process_update_to_websocket(uuid4())
        assert mock_sync.call_count == expected_call_count


@pytest.mark.parametrize(
    "enabled,expected_call_count",
    [
        pytest.param(True, 2, id="enabled"),
        pytest.param(False, 0, id="disabled"),
    ],
)
@pytest.mark.asyncio
async def test_broadcast_process_update_async(enabled: bool, expected_call_count: int):
    with patch("orchestrator.websocket.websocket_manager") as mock_wsm:
        mock_wsm.enabled = enabled
        mock_wsm.broadcast_data = AsyncMock()
        await broadcast_process_update_to_websocket_async(uuid4())
        assert mock_wsm.broadcast_data.await_count == expected_call_count


# --- sync wrappers ---


@patch("orchestrator.websocket.anyio")
def test_sync_broadcast_invalidate_cache(mock_anyio):
    cache_obj = {"type": "test"}
    sync_broadcast_invalidate_cache(cache_obj)
    mock_anyio.run.assert_called_once_with(broadcast_invalidate_cache, cache_obj)


@patch("orchestrator.websocket.anyio")
def test_sync_invalidate_subscription_cache(mock_anyio):
    sub_id = uuid4()
    sync_invalidate_subscription_cache(sub_id, True)
    mock_anyio.run.assert_called_once_with(invalidate_subscription_cache, sub_id, True)

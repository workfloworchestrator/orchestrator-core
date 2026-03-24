# Copyright 2019-2022 SURF.
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

"""Tests for RedisDistLockManager: connection lifecycle, lock acquire/release, namespaced keys, and LockError handling (documents logger.Exception bug)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import LockError

from orchestrator.distlock.managers.redis_distlock_manager import RedisDistLockManager


@pytest.fixture
def redis_dsn():
    return "redis://localhost:6379/0"


@pytest.fixture
def manager(redis_dsn):
    return RedisDistLockManager(redis_dsn)


@pytest.fixture
def connected_manager(manager):
    manager.redis_conn = AsyncMock()
    return manager


# --- connect / disconnect ---


async def test_connect_creates_client(manager: RedisDistLockManager) -> None:
    mock_client = AsyncMock()
    with patch(
        "orchestrator.distlock.managers.redis_distlock_manager.create_redis_asyncio_client",
        return_value=mock_client,
    ):
        await manager.connect_redis()
    assert manager.redis_conn is mock_client


async def test_disconnect_closes_connection(connected_manager: RedisDistLockManager) -> None:
    await connected_manager.disconnect_redis()
    connected_manager.redis_conn.close.assert_awaited_once()


async def test_disconnect_noop_when_not_connected(manager: RedisDistLockManager) -> None:
    await manager.disconnect_redis()


# --- get_lock ---


async def test_get_lock_without_connection_returns_none(manager: RedisDistLockManager) -> None:
    assert await manager.get_lock("resource", 30) is None


async def test_get_lock_acquire_success(connected_manager: RedisDistLockManager) -> None:
    mock_lock = AsyncMock()
    mock_lock.acquire = AsyncMock(return_value=True)
    with patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock):
        assert await connected_manager.get_lock("resource", 30) is mock_lock


async def test_get_lock_acquire_failure_returns_none(connected_manager: RedisDistLockManager) -> None:
    mock_lock = AsyncMock()
    mock_lock.acquire = AsyncMock(return_value=False)
    with patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock):
        assert await connected_manager.get_lock("resource", 30) is None


async def test_get_lock_constructs_namespaced_key(connected_manager: RedisDistLockManager) -> None:
    mock_lock = AsyncMock()
    mock_lock.acquire = AsyncMock(return_value=True)
    with patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock) as mock_cls:
        await connected_manager.get_lock("my-resource", 30)
    assert mock_cls.call_args.kwargs["name"] == "orchestrator:distlock:my-resource"


async def test_get_lock_on_lock_error_raises_attribute_error(connected_manager: RedisDistLockManager) -> None:
    """Documents logger.Exception bug — LockError except-branch crashes with AttributeError."""
    with (
        patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", side_effect=LockError("Redis error")),
        pytest.raises(AttributeError),
    ):
        await connected_manager.get_lock("resource", 30)


# --- release_lock ---


async def test_release_lock_without_connection_is_noop(manager: RedisDistLockManager) -> None:
    mock_lock = AsyncMock()
    await manager.release_lock(mock_lock)
    mock_lock.release.assert_not_awaited()


async def test_release_lock_calls_release(connected_manager: RedisDistLockManager) -> None:
    mock_lock = AsyncMock()
    await connected_manager.release_lock(mock_lock)
    mock_lock.release.assert_awaited_once()


async def test_release_lock_error_raises_attribute_error(connected_manager: RedisDistLockManager) -> None:
    """Documents logger.Exception bug — same as get_lock."""
    mock_lock = AsyncMock()
    mock_lock.release = AsyncMock(side_effect=LockError("already released"))
    with pytest.raises(AttributeError):
        await connected_manager.release_lock(mock_lock)


# --- release_sync ---


def test_release_sync_creates_sync_client(connected_manager: RedisDistLockManager) -> None:
    mock_redis_conn = MagicMock()
    mock_sync_lock = MagicMock()
    mock_async_lock = MagicMock()
    mock_async_lock.name = "orchestrator:distlock:resource"
    mock_async_lock.timeout = 30.0
    mock_async_lock.local = MagicMock()

    with (
        patch(
            "orchestrator.distlock.managers.redis_distlock_manager.create_redis_client",
            return_value=mock_redis_conn,
        ),
        patch(
            "orchestrator.distlock.managers.redis_distlock_manager.SyncLock",
            return_value=mock_sync_lock,
        ),
        patch("orchestrator.distlock.managers.redis_distlock_manager.app_settings") as mock_settings,
    ):
        mock_settings.CACHE_URI.get_secret_value.return_value = "redis://localhost:6379/0"
        connected_manager.release_sync(mock_async_lock)

    mock_sync_lock.release.assert_called_once()
    mock_redis_conn.close.assert_called_once()

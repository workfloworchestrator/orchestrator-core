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
    """Manager with a mocked async redis connection."""
    manager.redis_conn = AsyncMock()
    return manager


class TestRedisDistLockManagerInit:
    def test_init_sets_redis_conn_to_none(self, manager):
        assert manager.redis_conn is None

    def test_init_stores_redis_address(self, manager, redis_dsn):
        assert manager.redis_address == redis_dsn

    def test_namespace_is_correct(self, manager):
        assert manager.namespace == "orchestrator:distlock"


class TestRedisDistLockManagerConnectDisconnect:
    async def test_connect_redis_creates_client(self, manager):
        mock_client = AsyncMock()
        with patch(
            "orchestrator.distlock.managers.redis_distlock_manager.create_redis_asyncio_client",
            return_value=mock_client,
        ):
            await manager.connect_redis()

        assert manager.redis_conn is mock_client

    async def test_disconnect_redis_closes_connection(self, connected_manager):
        await connected_manager.disconnect_redis()
        connected_manager.redis_conn.close.assert_awaited_once()

    async def test_disconnect_redis_when_not_connected_is_noop(self, manager):
        # Should not raise when redis_conn is None
        await manager.disconnect_redis()


class TestRedisDistLockManagerGetLock:
    async def test_get_lock_without_connection_returns_none(self, manager):
        result = await manager.get_lock("resource", 30)
        assert result is None

    async def test_get_lock_acquire_success_returns_lock(self, connected_manager):
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(return_value=True)

        with patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock):
            result = await connected_manager.get_lock("resource", 30)

        assert result is mock_lock

    async def test_get_lock_acquire_failure_returns_none(self, connected_manager):
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(return_value=False)

        with patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock):
            result = await connected_manager.get_lock("resource", 30)

        assert result is None

    async def test_get_lock_constructs_namespaced_key(self, connected_manager):
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(return_value=True)

        with patch(
            "orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock
        ) as mock_lock_cls:
            await connected_manager.get_lock("my-resource", 30)

        call_kwargs = mock_lock_cls.call_args.kwargs
        assert call_kwargs["name"] == "orchestrator:distlock:my-resource"

    async def test_get_lock_passes_expiration_as_float_timeout(self, connected_manager):
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(return_value=True)

        with patch(
            "orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock
        ) as mock_lock_cls:
            await connected_manager.get_lock("resource", 45)

        call_kwargs = mock_lock_cls.call_args.kwargs
        assert call_kwargs["timeout"] == 45.0
        assert isinstance(call_kwargs["timeout"], float)

    async def test_get_lock_uses_non_blocking_mode(self, connected_manager):
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(return_value=True)

        with patch(
            "orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock
        ) as mock_lock_cls:
            await connected_manager.get_lock("resource", 30)

        call_kwargs = mock_lock_cls.call_args.kwargs
        assert call_kwargs["blocking"] is False
        assert call_kwargs["thread_local"] is False

    async def test_get_lock_on_lock_error_raises_attribute_error(self, connected_manager):
        # NOTE: The source has a bug: `logger.Exception(...)` should be `logger.exception(...)`.
        # When a LockError is raised, the except-branch itself crashes with AttributeError.
        # This test documents the current (broken) behavior so it is caught by CI if fixed.
        with (
            patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", side_effect=LockError("Redis error")),
            pytest.raises(AttributeError),
        ):
            await connected_manager.get_lock("resource", 30)

    async def test_get_lock_on_acquire_lock_error_raises_attribute_error(self, connected_manager):
        # NOTE: Same bug: `logger.Exception(...)` crashes the except-branch with AttributeError.
        mock_lock = AsyncMock()
        mock_lock.acquire = AsyncMock(side_effect=LockError("acquire failed"))

        with (
            patch("orchestrator.distlock.managers.redis_distlock_manager.Lock", return_value=mock_lock),
            pytest.raises(AttributeError),
        ):
            await connected_manager.get_lock("resource", 30)


class TestRedisDistLockManagerReleaseLock:
    async def test_release_lock_without_connection_is_noop(self, manager):
        mock_lock = AsyncMock()
        await manager.release_lock(mock_lock)
        mock_lock.release.assert_not_awaited()

    async def test_release_lock_calls_lock_release(self, connected_manager):
        mock_lock = AsyncMock()
        await connected_manager.release_lock(mock_lock)
        mock_lock.release.assert_awaited_once()

    async def test_release_lock_on_lock_error_raises_attribute_error(self, connected_manager):
        # NOTE: Same bug as get_lock: `logger.Exception(...)` should be `logger.exception(...)`.
        # The LockError is caught but the except-branch crashes with AttributeError.
        mock_lock = AsyncMock()
        mock_lock.release = AsyncMock(side_effect=LockError("already released"))
        with pytest.raises(AttributeError):
            await connected_manager.release_lock(mock_lock)


class TestRedisDistLockManagerReleaseSync:
    def test_release_sync_creates_sync_client_and_releases(self, connected_manager):
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

    def test_release_sync_on_lock_error_raises_attribute_error(self, connected_manager):
        # NOTE: Same `logger.Exception` bug — the LockError except-branch crashes with AttributeError.
        # The `finally` block does still run, so redis_conn.close() IS called before the error propagates.
        mock_redis_conn = MagicMock()
        mock_sync_lock = MagicMock()
        mock_sync_lock.release.side_effect = LockError("already released")
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
            pytest.raises(AttributeError),
        ):
            mock_settings.CACHE_URI.get_secret_value.return_value = "redis://localhost:6379/0"
            connected_manager.release_sync(mock_async_lock)

        # finally block still closes the redis connection even when the except-branch fails
        mock_redis_conn.close.assert_called_once()

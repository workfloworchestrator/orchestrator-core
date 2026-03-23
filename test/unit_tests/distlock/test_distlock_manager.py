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
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.distlock import WrappedDistLockManager, empty_fn
from orchestrator.distlock.distlock_manager import DistLockManager
from orchestrator.distlock.managers.memory_distlock_manager import MemoryDistLockManager
from orchestrator.distlock.managers.redis_distlock_manager import RedisDistLockManager


class TestDistLockManagerInit:
    def test_no_backend_uses_memory_manager(self):
        mgr = DistLockManager(enabled=True)
        assert isinstance(mgr._backend, MemoryDistLockManager)

    def test_backend_redis_with_dsn_uses_redis_manager(self):
        mgr = DistLockManager(enabled=True, backend="redis", redis_dsn="redis://localhost:6379/0")
        assert isinstance(mgr._backend, RedisDistLockManager)

    def test_backend_redis_without_dsn_falls_back_to_memory(self):
        mgr = DistLockManager(enabled=True, backend="redis", redis_dsn=None)
        assert isinstance(mgr._backend, MemoryDistLockManager)

    def test_backend_other_value_uses_memory(self):
        mgr = DistLockManager(enabled=True, backend="unknown")
        assert isinstance(mgr._backend, MemoryDistLockManager)

    def test_initial_connected_is_false(self):
        mgr = DistLockManager(enabled=True)
        assert mgr.connected is False

    def test_enabled_flag_is_stored(self):
        mgr = DistLockManager(enabled=False)
        assert mgr.enabled is False


class TestDistLockManagerConnectRedis:
    async def test_connect_redis_sets_connected_true(self):
        mgr = DistLockManager(enabled=True)
        mgr._backend = AsyncMock()
        await mgr.connect_redis()
        assert mgr.connected is True
        mgr._backend.connect_redis.assert_awaited_once()

    async def test_connect_redis_idempotent_when_already_connected(self):
        mgr = DistLockManager(enabled=True)
        mgr._backend = AsyncMock()
        mgr.connected = True
        await mgr.connect_redis()
        mgr._backend.connect_redis.assert_not_awaited()


class TestDistLockManagerDisconnectRedis:
    async def test_disconnect_redis_sets_connected_false(self):
        mgr = DistLockManager(enabled=True)
        mgr._backend = AsyncMock()
        mgr.connected = True
        await mgr.disconnect_redis()
        assert mgr.connected is False
        mgr._backend.disconnect_redis.assert_awaited_once()

    async def test_disconnect_redis_skipped_when_not_connected(self):
        mgr = DistLockManager(enabled=True)
        mgr._backend = AsyncMock()
        mgr.connected = False
        await mgr.disconnect_redis()
        mgr._backend.disconnect_redis.assert_not_awaited()


class TestDistLockManagerGetLock:
    async def test_get_lock_delegates_to_backend(self):
        mgr = DistLockManager(enabled=True)
        mock_lock = MagicMock()
        mgr._backend = AsyncMock()
        mgr._backend.get_lock = AsyncMock(return_value=mock_lock)
        result = await mgr.get_lock("resource", 30)
        assert result is mock_lock
        mgr._backend.get_lock.assert_awaited_once_with("resource", 30)


class TestDistLockManagerReleaseLock:
    async def test_release_lock_delegates_to_backend(self):
        mgr = DistLockManager(enabled=True)
        mock_lock = MagicMock()
        mgr._backend = AsyncMock()
        await mgr.release_lock(mock_lock)
        mgr._backend.release_lock.assert_awaited_once_with(mock_lock)


class TestDistLockManagerReleaseSync:
    def test_release_sync_delegates_to_backend(self):
        mgr = DistLockManager(enabled=True)
        mock_lock = MagicMock()
        mgr._backend = MagicMock()
        mgr.release_sync(mock_lock)
        mgr._backend.release_sync.assert_called_once_with(mock_lock)


class TestWrappedDistLockManagerNoWrappee:
    def test_attr_with_underscore_returns_none_when_no_wrappee(self):
        wrapped = WrappedDistLockManager()
        result = wrapped.connect_redis
        assert result is None

    def test_attr_with_underscore_logs_warning_when_no_wrappee(self, caplog):
        wrapped = WrappedDistLockManager()
        with caplog.at_level(logging.WARNING, logger="orchestrator.distlock"):
            result = wrapped.some_method
        assert result is None
        assert "No DistLockManager configured" in caplog.text

    def test_attr_without_underscore_raises_runtime_warning_when_no_wrappee(self):
        wrapped = WrappedDistLockManager()
        with pytest.raises(RuntimeWarning):
            _ = wrapped.enabled

    def test_attr_without_underscore_raises_runtime_warning_for_any_plain_name(self):
        wrapped = WrappedDistLockManager()
        with pytest.raises(RuntimeWarning):
            _ = wrapped.getlock


class TestWrappedDistLockManagerDisabled:
    def test_non_enabled_attr_returns_empty_fn_when_disabled(self):
        inner = DistLockManager(enabled=False)
        wrapped = WrappedDistLockManager(wrappee=inner)
        result = wrapped.get_lock
        assert result is empty_fn

    def test_enabled_attr_returns_actual_value_when_disabled(self):
        inner = DistLockManager(enabled=False)
        wrapped = WrappedDistLockManager(wrappee=inner)
        assert wrapped.enabled is False

    async def test_empty_fn_is_awaitable_and_returns_none(self):
        result = await empty_fn("arg1", key="value")
        assert result is None


class TestWrappedDistLockManagerEnabled:
    def test_get_lock_delegates_to_wrapped_when_enabled(self):
        inner = DistLockManager(enabled=True)
        mock_backend = AsyncMock()
        inner._backend = mock_backend
        wrapped = WrappedDistLockManager(wrappee=inner)
        method = wrapped.get_lock
        assert method == inner.get_lock

    def test_enabled_returns_true_when_enabled(self):
        inner = DistLockManager(enabled=True)
        wrapped = WrappedDistLockManager(wrappee=inner)
        assert wrapped.enabled is True


class TestWrappedDistLockManagerUpdate:
    def test_update_sets_new_wrappee(self):
        wrapped = WrappedDistLockManager()
        new_inner = DistLockManager(enabled=True)
        wrapped.update(new_inner)
        assert wrapped.wrapped_distlock_manager is new_inner

    def test_update_replaces_old_wrappee(self):
        first = DistLockManager(enabled=False)
        second = DistLockManager(enabled=True)
        wrapped = WrappedDistLockManager(wrappee=first)
        wrapped.update(second)
        assert wrapped.enabled is True


class TestInitDistLockManager:
    @pytest.fixture(autouse=True)
    def _save_restore_wrapped_manager(self):
        """Preserve the global wrapped_distlock_manager state across tests."""
        from orchestrator.distlock import wrapped_distlock_manager

        original = wrapped_distlock_manager.wrapped_distlock_manager
        yield
        wrapped_distlock_manager.wrapped_distlock_manager = original

    def test_init_distlock_manager_returns_distlock_manager(self):
        from orchestrator.distlock import init_distlock_manager

        mock_settings = MagicMock()
        mock_settings.ENABLE_DISTLOCK_MANAGER = True
        mock_settings.DISTLOCK_BACKEND = None
        mock_settings.CACHE_URI.get_secret_value.return_value = None

        result = init_distlock_manager(mock_settings)
        # Returns the cast distlock_manager (a WrappedDistLockManager)
        assert result is not None

    def test_init_distlock_manager_with_redis_backend(self):
        from orchestrator.distlock import init_distlock_manager, wrapped_distlock_manager

        mock_settings = MagicMock()
        mock_settings.ENABLE_DISTLOCK_MANAGER = True
        mock_settings.DISTLOCK_BACKEND = "redis"
        mock_settings.CACHE_URI.get_secret_value.return_value = "redis://localhost:6379/0"

        init_distlock_manager(mock_settings)
        assert isinstance(wrapped_distlock_manager.wrapped_distlock_manager._backend, RedisDistLockManager)

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
from threading import Lock
from time import sleep

import pytest

from orchestrator.distlock.managers.memory_distlock_manager import MemoryDistLockManager


@pytest.fixture
def manager():
    return MemoryDistLockManager()


class TestMemoryDistLockManagerInit:
    def test_init_starts_daemon_thread(self, manager):
        assert manager.daemon is True
        assert manager.is_alive()

    def test_init_sets_thread_name(self, manager):
        assert manager.name == "MemoryDistLockExpirationThread"


class TestMemoryDistLockManagerConnectDisconnect:
    async def test_connect_redis_is_noop(self, manager):
        # Should not raise and return None
        result = await manager.connect_redis()
        assert result is None

    async def test_disconnect_redis_is_noop(self, manager):
        # Should not raise and return None
        result = await manager.disconnect_redis()
        assert result is None


class TestMemoryDistLockManagerGetLock:
    async def test_get_lock_returns_lock_on_first_acquire(self, manager):
        lock = await manager.get_lock("resource-a", 60)
        assert lock is not None

    async def test_get_lock_stores_lock_in_locks_dict(self, manager):
        await manager.get_lock("resource-b", 60)
        assert "resource-b" in MemoryDistLockManager.locks

    async def test_get_lock_double_acquire_returns_none(self, manager):
        await manager.get_lock("resource-c", 60)
        second = await manager.get_lock("resource-c", 60)
        assert second is None

    async def test_get_lock_different_resources_both_succeed(self, manager):
        lock_a = await manager.get_lock("resource-d", 60)
        lock_b = await manager.get_lock("resource-e", 60)
        assert lock_a is not None
        assert lock_b is not None

    async def test_get_lock_sets_expiry_time(self, manager):
        from time import time

        before = time()
        await manager.get_lock("resource-f", 10)
        _, expire_at = MemoryDistLockManager.locks["resource-f"]
        assert expire_at >= before + 10


class TestMemoryDistLockManagerReleaseLock:
    async def test_release_lock_removes_from_locks_dict(self, manager):
        lock = await manager.get_lock("resource-g", 60)
        assert lock is not None
        await manager.release_lock(lock)
        assert "resource-g" not in MemoryDistLockManager.locks

    async def test_release_lock_allows_reacquire(self, manager):
        lock = await manager.get_lock("resource-h", 60)
        assert lock is not None
        await manager.release_lock(lock)
        new_lock = await manager.get_lock("resource-h", 60)
        assert new_lock is not None

    async def test_release_lock_then_double_acquire_fails(self, manager):
        lock = await manager.get_lock("resource-i", 60)
        assert lock is not None
        await manager.release_lock(lock)
        await manager.get_lock("resource-i", 60)
        second = await manager.get_lock("resource-i", 60)
        assert second is None


class TestMemoryDistLockManagerReleaseSync:
    def test_release_sync_releases_lock(self, manager):
        import asyncio

        lock = asyncio.run(manager.get_lock("resource-j", 60))
        assert lock is not None
        manager.release_sync(lock)
        assert "resource-j" not in MemoryDistLockManager.locks

    def test_release_sync_allows_reacquire(self, manager):
        import asyncio

        lock = asyncio.run(manager.get_lock("resource-k", 60))
        assert lock is not None
        manager.release_sync(lock)
        new_lock = asyncio.run(manager.get_lock("resource-k", 60))
        assert new_lock is not None


class TestMemoryDistLockManagerExpiration:
    async def test_expired_lock_is_removed_by_background_thread(self, manager):
        lock = await manager.get_lock("short-lived", 0)
        assert lock is not None
        sleep(0.2)
        assert "short-lived" not in MemoryDistLockManager.locks

    async def test_non_expired_lock_is_not_removed(self, manager):
        lock = await manager.get_lock("long-lived", 60)
        assert lock is not None
        sleep(0.2)
        assert "long-lived" in MemoryDistLockManager.locks

    async def test_multiple_locks_only_expired_ones_removed(self, manager):
        await manager.get_lock("expires-soon", 0)
        await manager.get_lock("stays-alive", 60)
        sleep(0.2)
        assert "expires-soon" not in MemoryDistLockManager.locks
        assert "stays-alive" in MemoryDistLockManager.locks

    async def test_lock_can_be_reacquired_after_expiration(self, manager):
        lock = await manager.get_lock("reacquire-me", 0)
        assert lock is not None
        sleep(0.2)
        new_lock = await manager.get_lock("reacquire-me", 60)
        assert new_lock is not None


class TestMemoryDistLockManagerReleaseLockUnknown:
    async def test_release_lock_unknown_lock_raises(self, manager):
        unknown_lock = Lock()
        unknown_lock.acquire()
        with pytest.raises(UnboundLocalError):
            await manager.release_lock(unknown_lock)

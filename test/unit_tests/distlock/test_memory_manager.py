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

"""Tests for MemoryDistLockManager: acquire/release, double-acquire blocking, expiration by background thread, and sync release."""

import asyncio
from threading import Lock
from time import sleep, time

import pytest

from orchestrator.core.distlock.managers.memory_distlock_manager import MemoryDistLockManager


@pytest.fixture
def manager():
    return MemoryDistLockManager()


def test_init_starts_daemon_thread(manager: MemoryDistLockManager) -> None:
    assert manager.daemon is True
    assert manager.is_alive()


# --- get_lock / release_lock ---


async def test_get_lock_returns_lock(manager: MemoryDistLockManager) -> None:
    lock = await manager.get_lock("resource-a", 60)
    assert lock is not None
    assert "resource-a" in MemoryDistLockManager.locks


async def test_double_acquire_returns_none(manager: MemoryDistLockManager) -> None:
    await manager.get_lock("resource-c", 60)
    assert await manager.get_lock("resource-c", 60) is None


async def test_get_lock_sets_expiry(manager: MemoryDistLockManager) -> None:
    before = time()
    await manager.get_lock("resource-f", 10)
    _, expire_at = MemoryDistLockManager.locks["resource-f"]
    assert expire_at >= before + 10


async def test_release_allows_reacquire(manager: MemoryDistLockManager) -> None:
    lock = await manager.get_lock("resource-h", 60)
    assert lock is not None
    await manager.release_lock(lock)
    assert await manager.get_lock("resource-h", 60) is not None


def test_release_sync(manager: MemoryDistLockManager) -> None:
    lock = asyncio.run(manager.get_lock("resource-j", 60))
    assert lock is not None
    manager.release_sync(lock)
    assert "resource-j" not in MemoryDistLockManager.locks


# --- expiration ---


async def test_expired_lock_removed_by_background_thread(manager: MemoryDistLockManager) -> None:
    await manager.get_lock("short-lived", 0)
    sleep(0.2)
    assert "short-lived" not in MemoryDistLockManager.locks


async def test_non_expired_lock_survives(manager: MemoryDistLockManager) -> None:
    await manager.get_lock("long-lived", 60)
    sleep(0.2)
    assert "long-lived" in MemoryDistLockManager.locks


# --- edge cases ---


async def test_release_unknown_lock_raises(manager: MemoryDistLockManager) -> None:
    unknown_lock = Lock()
    unknown_lock.acquire()
    with pytest.raises(UnboundLocalError):
        await manager.release_lock(unknown_lock)

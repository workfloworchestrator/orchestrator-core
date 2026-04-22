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

"""Tests for DistLockManager (backend selection, connect/disconnect idempotency) and WrappedDistLockManager (delegation, disabled mode, update)."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.core.distlock import WrappedDistLockManager, empty_fn
from orchestrator.core.distlock.distlock_manager import DistLockManager
from orchestrator.core.distlock.managers.memory_distlock_manager import MemoryDistLockManager
from orchestrator.core.distlock.managers.redis_distlock_manager import RedisDistLockManager

# --- DistLockManager backend selection ---


@pytest.mark.parametrize(
    "backend,redis_dsn,expected_type",
    [
        pytest.param(None, None, MemoryDistLockManager, id="no-backend-memory"),
        pytest.param("redis", "redis://localhost:6379/0", RedisDistLockManager, id="redis-with-dsn"),
        pytest.param("redis", None, MemoryDistLockManager, id="redis-no-dsn-fallback"),
        pytest.param("unknown", None, MemoryDistLockManager, id="unknown-fallback"),
    ],
)
def test_distlock_manager_backend_selection(backend: str | None, redis_dsn: str | None, expected_type: type) -> None:
    kwargs: dict = {"enabled": True}
    if backend:
        kwargs["backend"] = backend
    if redis_dsn:
        kwargs["redis_dsn"] = redis_dsn
    mgr = DistLockManager(**kwargs)
    assert isinstance(mgr._backend, expected_type)


# --- DistLockManager connect/disconnect ---


async def test_connect_redis_sets_connected() -> None:
    mgr = DistLockManager(enabled=True)
    mgr._backend = AsyncMock()
    await mgr.connect_redis()
    assert mgr.connected is True
    mgr._backend.connect_redis.assert_awaited_once()


async def test_connect_redis_idempotent() -> None:
    mgr = DistLockManager(enabled=True)
    mgr._backend = AsyncMock()
    mgr.connected = True
    await mgr.connect_redis()
    mgr._backend.connect_redis.assert_not_awaited()


async def test_disconnect_redis_sets_connected_false() -> None:
    mgr = DistLockManager(enabled=True)
    mgr._backend = AsyncMock()
    mgr.connected = True
    await mgr.disconnect_redis()
    assert mgr.connected is False


async def test_disconnect_redis_skipped_when_not_connected() -> None:
    mgr = DistLockManager(enabled=True)
    mgr._backend = AsyncMock()
    await mgr.disconnect_redis()
    mgr._backend.disconnect_redis.assert_not_awaited()


# --- WrappedDistLockManager ---


def test_wrapped_no_wrappee_returns_none_for_method(caplog: pytest.LogCaptureFixture) -> None:
    wrapped = WrappedDistLockManager()
    with caplog.at_level(logging.WARNING, logger="orchestrator.core.distlock"):
        assert wrapped.connect_redis is None
    assert "No DistLockManager configured" in caplog.text


def test_wrapped_no_wrappee_raises_for_property() -> None:
    wrapped = WrappedDistLockManager()
    with pytest.raises(RuntimeWarning):
        _ = wrapped.enabled


def test_wrapped_disabled_returns_empty_fn() -> None:
    inner = DistLockManager(enabled=False)
    wrapped = WrappedDistLockManager(wrappee=inner)
    assert wrapped.get_lock is empty_fn


def test_wrapped_enabled_delegates() -> None:
    inner = DistLockManager(enabled=True)
    inner._backend = AsyncMock()
    wrapped = WrappedDistLockManager(wrappee=inner)
    assert wrapped.get_lock == inner.get_lock


async def test_empty_fn_returns_none() -> None:
    assert await empty_fn(("arg",)) is None  # type: ignore[func-returns-value]


def test_wrapped_update_replaces_wrappee() -> None:
    first = DistLockManager(enabled=False)
    second = DistLockManager(enabled=True)
    wrapped = WrappedDistLockManager(wrappee=first)
    wrapped.update(second)
    assert wrapped.enabled is True


# --- init_distlock_manager ---


@pytest.fixture
def _save_restore_wrapped_manager():
    from orchestrator.core.distlock import wrapped_distlock_manager

    original = wrapped_distlock_manager.wrapped_distlock_manager
    yield
    wrapped_distlock_manager.wrapped_distlock_manager = original


@pytest.mark.usefixtures("_save_restore_wrapped_manager")
def test_init_distlock_manager_redis_backend() -> None:
    from orchestrator.core.distlock import init_distlock_manager, wrapped_distlock_manager

    mock_settings = MagicMock()
    mock_settings.ENABLE_DISTLOCK_MANAGER = True
    mock_settings.DISTLOCK_BACKEND = "redis"
    mock_settings.CACHE_URI.get_secret_value.return_value = "redis://localhost:6379/0"

    init_distlock_manager(mock_settings)
    mgr = wrapped_distlock_manager.wrapped_distlock_manager
    assert mgr is not None
    assert isinstance(mgr._backend, RedisDistLockManager)

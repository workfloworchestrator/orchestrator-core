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

"""Tests for the engine arguments of the database connection pool and its settings."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, QueuePool, StaticPool

import orchestrator.core.db.database as database_module
from orchestrator.core.db.database import Database, make_engine_arguments
from orchestrator.core.settings import (
    DATABASE_MAX_OVERFLOW_DEFAULT,
    DATABASE_POOL_SIZE_DEFAULT,
    DATABASE_POOL_TIMEOUT_DEFAULT,
    AppSettings,
    app_settings,
)

DB_URL = "postgresql+psycopg://nwa:nwa@localhost/orchestrator-core"

POOL_SETTING_NAMES = ("DATABASE_POOL_SIZE", "DATABASE_MAX_OVERFLOW", "DATABASE_POOL_TIMEOUT")
ENGINE_KEYS = ("pool_size", "max_overflow", "pool_timeout")


def pool_settings(**overrides):
    """A stand-in for AppSettings that, like the real one, always carries all three settings."""
    values = {
        "DATABASE_POOL_SIZE": DATABASE_POOL_SIZE_DEFAULT,
        "DATABASE_MAX_OVERFLOW": DATABASE_MAX_OVERFLOW_DEFAULT,
        "DATABASE_POOL_TIMEOUT": DATABASE_POOL_TIMEOUT_DEFAULT,
    }
    return SimpleNamespace(**{**values, **overrides})


@pytest.fixture(autouse=True)
def unset_pool_env_vars(monkeypatch) -> None:
    """Keep the developer's environment from leaking into the AppSettings defaults under test."""
    for name in POOL_SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)


# --- AppSettings ---


@pytest.mark.parametrize(
    "env_name,attribute,value",
    [
        pytest.param("DATABASE_POOL_SIZE", "DATABASE_POOL_SIZE", 10, id="pool-size"),
        pytest.param("DATABASE_MAX_OVERFLOW", "DATABASE_MAX_OVERFLOW", 20, id="max-overflow"),
        pytest.param("DATABASE_POOL_TIMEOUT", "DATABASE_POOL_TIMEOUT", 5, id="pool-timeout"),
    ],
)
def test_pool_settings_from_env(monkeypatch, env_name, attribute, value) -> None:
    monkeypatch.setenv(env_name, str(value))

    assert getattr(AppSettings(), attribute) == value


@pytest.mark.parametrize(
    "attribute,value",
    [
        pytest.param("DATABASE_POOL_SIZE", 0, id="pool-size-zero"),
        pytest.param("DATABASE_POOL_SIZE", -1, id="pool-size-negative"),
        pytest.param("DATABASE_MAX_OVERFLOW", -1, id="max-overflow-negative"),
        pytest.param("DATABASE_POOL_TIMEOUT", -1, id="pool-timeout-negative"),
    ],
)
def test_pool_settings_are_validated(attribute, value) -> None:
    with pytest.raises(ValidationError):
        AppSettings(**{attribute: value})


@pytest.mark.parametrize(
    "attribute,value",
    [
        pytest.param("DATABASE_MAX_OVERFLOW", 0, id="max-overflow-can-disable-overflow"),
        pytest.param("DATABASE_POOL_TIMEOUT", 0, id="pool-timeout-can-fail-fast"),
    ],
)
def test_pool_settings_boundary_values_are_accepted(attribute, value) -> None:
    assert getattr(AppSettings(**{attribute: value}), attribute) == value


# --- make_engine_arguments ---


@pytest.mark.parametrize(
    "settings,expected",
    [
        pytest.param(
            {"DATABASE_POOL_SIZE": 10, "DATABASE_MAX_OVERFLOW": 5, "DATABASE_POOL_TIMEOUT": 3},
            {"pool_size": 10, "max_overflow": 5, "pool_timeout": 3},
            id="all-set",
        ),
        pytest.param({"DATABASE_POOL_SIZE": 10}, {"pool_size": 10}, id="only-pool-size"),
        pytest.param({"DATABASE_MAX_OVERFLOW": 5}, {"max_overflow": 5}, id="only-max-overflow"),
        pytest.param({"DATABASE_POOL_TIMEOUT": 0}, {"pool_timeout": 0}, id="timeout-zero-is-a-value"),
        pytest.param(
            {
                "DATABASE_POOL_SIZE": DATABASE_POOL_SIZE_DEFAULT,
                "DATABASE_MAX_OVERFLOW": DATABASE_MAX_OVERFLOW_DEFAULT,
                "DATABASE_POOL_TIMEOUT": DATABASE_POOL_TIMEOUT_DEFAULT,
            },
            {
                "pool_size": DATABASE_POOL_SIZE_DEFAULT,
                "max_overflow": DATABASE_MAX_OVERFLOW_DEFAULT,
                "pool_timeout": DATABASE_POOL_TIMEOUT_DEFAULT,
            },
            id="defaults",
        ),
    ],
)
def test_make_engine_arguments_applies_settings(settings, expected) -> None:
    arguments = make_engine_arguments(pool_settings(**settings))

    # Every pool key is present: a setting overrides the shipped value, the others keep it.
    assert {key: value for key, value in arguments.items() if key in ENGINE_KEYS} == {
        "pool_size": DATABASE_POOL_SIZE_DEFAULT,
        "max_overflow": DATABASE_MAX_OVERFLOW_DEFAULT,
        "pool_timeout": DATABASE_POOL_TIMEOUT_DEFAULT,
        **expected,
    }
    # The non-pool arguments are always passed through.
    assert arguments["pool_pre_ping"] is True
    assert arguments["connect_args"] == database_module.ENGINE_ARGUMENTS["connect_args"]


@pytest.mark.parametrize(
    "engine_key,setting_name",
    [(engine_key, setting_name) for engine_key, (setting_name, _) in database_module.POOL_SETTINGS.items()],
)
def test_make_engine_arguments_keeps_a_patched_pool_key(engine_key, setting_name) -> None:
    """A downstream orchestrator that patches a pool key in ENGINE_ARGUMENTS keeps control over it."""
    with patch.object(database_module, "ENGINE_ARGUMENTS", {**database_module.ENGINE_ARGUMENTS, engine_key: 3}):
        arguments = make_engine_arguments(pool_settings(**{setting_name: 99}))

    assert arguments[engine_key] == 3


def test_make_engine_arguments_does_not_mutate_engine_arguments() -> None:
    original = dict(database_module.ENGINE_ARGUMENTS)
    make_engine_arguments(pool_settings(DATABASE_POOL_SIZE=1, DATABASE_MAX_OVERFLOW=1, DATABASE_POOL_TIMEOUT=1))

    assert database_module.ENGINE_ARGUMENTS == original


@pytest.mark.parametrize(
    "engine_arguments",
    [
        pytest.param({}, id="empty-dict"),
        pytest.param({"pool_pre_ping": False}, id="no-pool-keys"),
    ],
)
def test_make_engine_arguments_survives_a_replaced_engine_arguments(engine_arguments) -> None:
    """Downstream orchestrators replace ENGINE_ARGUMENTS, so nothing in it may be assumed to exist."""
    with patch.object(database_module, "ENGINE_ARGUMENTS", engine_arguments):
        arguments = make_engine_arguments(pool_settings())

    # The replaced dict is kept and the pool keys come from the settings.
    assert {key: value for key, value in arguments.items() if key in engine_arguments} == engine_arguments
    assert arguments["pool_size"] == DATABASE_POOL_SIZE_DEFAULT
    assert arguments["max_overflow"] == DATABASE_MAX_OVERFLOW_DEFAULT
    assert arguments["pool_timeout"] == DATABASE_POOL_TIMEOUT_DEFAULT


@pytest.mark.parametrize(
    "engine_arguments",
    [
        pytest.param({"poolclass": NullPool}, id="null-pool"),
        pytest.param({"poolclass": StaticPool}, id="static-pool"),
        pytest.param({"pool": object()}, id="pool-instance"),
    ],
)
def test_make_engine_arguments_skips_pool_settings_for_a_non_queue_pool(engine_arguments) -> None:
    """Replacing ENGINE_ARGUMENTS with a pool that has no queue must not get QueuePool-only options."""
    with patch.object(database_module, "ENGINE_ARGUMENTS", engine_arguments):
        arguments = make_engine_arguments(pool_settings(DATABASE_POOL_SIZE=3))

    assert arguments == engine_arguments


@pytest.mark.parametrize(
    "poolclass",
    [pytest.param(QueuePool, id="queue-pool"), pytest.param(AsyncAdaptedQueuePool, id="async-queue-pool")],
)
def test_make_engine_arguments_applies_pool_settings_to_a_queue_pool(poolclass) -> None:
    with patch.object(database_module, "ENGINE_ARGUMENTS", {"poolclass": poolclass}):
        arguments = make_engine_arguments(pool_settings(DATABASE_POOL_SIZE=3))

    assert arguments["pool_size"] == 3


def test_database_starts_with_a_null_pool_replacement() -> None:
    with patch.object(database_module, "ENGINE_ARGUMENTS", {"poolclass": NullPool}):
        db = Database(DB_URL, pool_settings())

    assert isinstance(db.engine.pool, NullPool)


# --- Database ---


@pytest.mark.parametrize(
    "pool_settings,expected_pool_size,expected_max_overflow,expected_timeout",
    [
        pytest.param(
            SimpleNamespace(DATABASE_POOL_SIZE=3, DATABASE_MAX_OVERFLOW=2, DATABASE_POOL_TIMEOUT=4),
            3,
            2,
            4,
            id="settings-win",
        ),
        pytest.param(
            SimpleNamespace(
                DATABASE_POOL_SIZE=DATABASE_POOL_SIZE_DEFAULT,
                DATABASE_MAX_OVERFLOW=DATABASE_MAX_OVERFLOW_DEFAULT,
                DATABASE_POOL_TIMEOUT=DATABASE_POOL_TIMEOUT_DEFAULT,
            ),
            60,
            10,
            30,
            id="settings-defaults",
        ),
    ],
)
def test_database_applies_pool_settings_to_both_engines(
    pool_settings, expected_pool_size, expected_max_overflow, expected_timeout
) -> None:
    test_database = Database(DB_URL, pool_settings)

    for engine in (test_database.engine, test_database.async_engine):
        pool = engine.pool
        assert pool.size() == expected_pool_size  # type: ignore[attr-defined]
        assert pool._max_overflow == expected_max_overflow  # type: ignore[attr-defined]
        assert pool._timeout == expected_timeout  # type: ignore[attr-defined]

    test_database.engine.dispose()
    asyncio.run(test_database.async_engine.dispose())


def test_database_defaults_to_application_pool_settings(monkeypatch) -> None:
    """The original one-argument constructor uses the application settings."""
    monkeypatch.setattr(app_settings, "DATABASE_POOL_SIZE", 7)

    test_database = Database(DB_URL)

    assert test_database.engine.pool.size() == 7  # type: ignore[attr-defined]
    test_database.engine.dispose()
    asyncio.run(test_database.async_engine.dispose())


def test_make_engine_arguments_applies_settings_over_a_default_valued_patch() -> None:
    """A patch equal to the built-in default is indistinguishable from the shipped value."""
    with patch.object(database_module, "ENGINE_ARGUMENTS", {**database_module.ENGINE_ARGUMENTS, "pool_size": 60}):
        arguments = make_engine_arguments(pool_settings(DATABASE_POOL_SIZE=7))

    assert arguments["pool_size"] == 7

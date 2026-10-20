# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

"""Unit tests for service resolution and fixture helpers in ``orchestrator.core.testing``."""

import sys
from pathlib import Path
from types import ModuleType
from unittest import mock

import pytest

from orchestrator.core.testing import services
from orchestrator.core.testing.fixtures import (
    NO_XDIST_WORKER,
    ORCHESTRATOR_MIGRATIONS_DIR,
    make_alembic_config,
    make_db_uri,
    xdist_worker_id,
)
from orchestrator.core.testing.services import (
    DEFAULT_POSTGRES_IMAGE,
    MODULE_REDIS_CLIENTS,
    ServiceURIs,
    patch_app_settings,
    postgres_image,
    provide_services,
    rebind_redis_clients,
)

DB_URI = "postgresql+psycopg://nwa:nwa@db/orchestrator-core-test"
CACHE_URI = "redis://cache:6379/0"


@pytest.fixture
def no_service_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URI", raising=False)
    monkeypatch.delenv("CACHE_URI", raising=False)


@pytest.mark.parametrize(
    "env_value,expected",
    [
        (None, DEFAULT_POSTGRES_IMAGE),
        ("", DEFAULT_POSTGRES_IMAGE),
        ("pgvector/pgvector:pg15", "pgvector/pgvector:pg15"),
    ],
)
def test_postgres_image(monkeypatch, env_value, expected):
    if env_value is None:
        monkeypatch.delenv(services.POSTGRES_IMAGE_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(services.POSTGRES_IMAGE_ENV_VAR, env_value)

    assert postgres_image() == expected


def test_provide_services_uses_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URI", DB_URI)
    monkeypatch.setenv("CACHE_URI", CACHE_URI)

    with mock.patch.object(services, "_testcontainers_services") as containers, provide_services() as uris:
        assert uris == ServiceURIs(database_uri=DB_URI, cache_uri=CACHE_URI)

    containers.assert_not_called()


@pytest.mark.parametrize(
    "env_var,value,missing",
    [
        ("DATABASE_URI", DB_URI, "CACHE_URI"),
        ("CACHE_URI", CACHE_URI, "DATABASE_URI"),
    ],
)
def test_provide_services_rejects_partial_environment(no_service_env, monkeypatch, env_var, value, missing):
    monkeypatch.setenv(env_var, value)

    with pytest.raises(RuntimeError, match=f"{missing} is not set"), provide_services():
        pass


def test_provide_services_falls_back_to_testcontainers_and_restores_environment(no_service_env):
    import os

    container_uris = ServiceURIs(database_uri=DB_URI, cache_uri=CACHE_URI)

    with mock.patch.object(services, "_testcontainers_services") as containers:
        containers.return_value.__enter__.return_value = container_uris
        with provide_services() as uris:
            assert uris is container_uris

    assert "DATABASE_URI" not in os.environ
    assert "CACHE_URI" not in os.environ


def test_provide_services_exports_container_uris_while_active(no_service_env):
    import os

    container_uris = ServiceURIs(database_uri=DB_URI, cache_uri=CACHE_URI)
    with mock.patch.object(services, "_testcontainers_services") as containers:
        containers.return_value.__enter__.return_value = container_uris
        with provide_services():
            assert os.environ["DATABASE_URI"] == DB_URI
            assert os.environ["CACHE_URI"] == CACHE_URI


def test_testcontainers_missing_raises_actionable_error(no_service_env):
    with (
        mock.patch.dict(sys.modules, {"testcontainers.postgres": None, "testcontainers.redis": None}),
        pytest.raises(RuntimeError, match=r"orchestrator-core\[testing\]"),
        provide_services(),
    ):
        pass


def test_rebind_redis_clients_replaces_clients_of_imported_modules():
    fake_modules = {name: ModuleType(name) for name, _, _ in MODULE_REDIS_CLIENTS}

    with (
        mock.patch.dict(sys.modules, fake_modules),
        mock.patch("orchestrator.core.utils.redis_client.create_redis_client", return_value="sync") as sync_factory,
        mock.patch(
            "orchestrator.core.utils.redis_client.create_redis_asyncio_client", return_value="async"
        ) as async_factory,
    ):
        rebind_redis_clients(CACHE_URI)

    assert {(name, attr): getattr(fake_modules[name], attr) for name, attr, _ in MODULE_REDIS_CLIENTS} == {
        (name, attr): "async" if is_async else "sync" for name, attr, is_async in MODULE_REDIS_CLIENTS
    }
    sync_factory.assert_called_with(CACHE_URI)
    async_factory.assert_called_with(CACHE_URI)


def test_rebind_redis_clients_skips_modules_not_imported():
    with (
        mock.patch.dict(sys.modules, {name: None for name, _, _ in MODULE_REDIS_CLIENTS}),
        mock.patch("orchestrator.core.utils.redis_client.create_redis_client") as sync_factory,
        mock.patch("orchestrator.core.utils.redis_client.create_redis_asyncio_client") as async_factory,
    ):
        rebind_redis_clients(CACHE_URI)

    sync_factory.assert_not_called()
    async_factory.assert_not_called()


def test_patch_app_settings():
    from orchestrator.core.settings import app_settings

    with (
        mock.patch.object(app_settings, "DATABASE_URI"),
        mock.patch.object(app_settings, "CACHE_URI"),
        mock.patch.object(services, "rebind_redis_clients") as rebind,
    ):
        patch_app_settings(ServiceURIs(database_uri=DB_URI, cache_uri=CACHE_URI))

        assert str(app_settings.DATABASE_URI.get_secret_value()) == DB_URI
        assert str(app_settings.CACHE_URI.get_secret_value()) == CACHE_URI
    rebind.assert_called_once_with(CACHE_URI)


@pytest.mark.parametrize(
    "env_value,expected",
    [(None, NO_XDIST_WORKER), ("gw3", "gw3")],
)
def test_xdist_worker_id(monkeypatch, env_value, expected):
    if env_value is None:
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    else:
        monkeypatch.setenv("PYTEST_XDIST_WORKER", env_value)

    assert xdist_worker_id() == expected


@pytest.mark.parametrize(
    "xdist_worker,expected",
    [
        (NO_XDIST_WORKER, DB_URI),
        ("gw0", f"{DB_URI}-gw0"),
    ],
)
def test_make_db_uri(xdist_worker, expected):
    assert make_db_uri(xdist_worker, DB_URI) == expected


def test_make_db_uri_keeps_password():
    assert make_db_uri("gw1", "postgresql+psycopg://user:secret@db/test") == (
        "postgresql+psycopg://user:secret@db/test-gw1"
    )


def test_make_alembic_config_defaults_to_core_migrations():
    cfg = make_alembic_config(DB_URI)

    assert cfg.get_main_option("script_location") == str(ORCHESTRATOR_MIGRATIONS_DIR)
    assert cfg.get_main_option("version_locations") == str(ORCHESTRATOR_MIGRATIONS_DIR / "versions" / "schema")
    assert cfg.get_main_option("sqlalchemy.url") == DB_URI


def test_make_alembic_config_extends_downstream_version_locations(tmp_path: Path):
    alembic_ini = tmp_path / "alembic.ini"
    alembic_ini.write_text(
        "[alembic]\nscript_location = %(here)s/migrations\nversion_locations = %(here)s/migrations/versions/schema\n"
    )

    cfg = make_alembic_config(DB_URI, alembic_ini)

    assert cfg.get_main_option("script_location") == f"{tmp_path}/migrations"
    assert cfg.get_main_option("version_locations") == (
        f"{tmp_path}/migrations/versions/schema {ORCHESTRATOR_MIGRATIONS_DIR / 'versions' / 'schema'}"
    )
    assert cfg.get_main_option("sqlalchemy.url") == DB_URI

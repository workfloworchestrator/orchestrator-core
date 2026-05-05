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

"""Service provider for integration tests.

Resolves how Postgres and Redis are made available to integration tests in this
order:

1. **Bring-your-own**: when ``DATABASE_URI`` and ``CACHE_URI`` are both set in
   the environment, integration tests use them as-is. This is what CI and
   ``docker compose -f docker/pytest-support/docker-compose.yaml up`` do.
2. **Testcontainers fallback**: when neither env var is set, and the
   ``testcontainers`` package is installed and Docker is reachable, ephemeral
   Postgres + Redis containers are started for the test session.
3. **Clear failure**: otherwise, abort with an actionable message.

Partial environment configuration (only one of the two URIs set) is rejected so
the test setup never silently mixes a real service with an ephemeral one.

This module is imported from ``test/integration_tests/conftest.py`` *before*
any ``orchestrator.*`` import so that ``DATABASE_URI`` and ``CACHE_URI`` are set
in ``os.environ`` before pydantic-settings constructs ``app_settings`` and
before modules like ``orchestrator.core.schedules.service`` capture
``app_settings.CACHE_URI`` at import time.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

DEFAULT_POSTGRES_IMAGE = "pgvector/pgvector:pg17"
DEFAULT_REDIS_IMAGE = "redis:7"
DEFAULT_POSTGRES_USER = "nwa"
DEFAULT_POSTGRES_PASSWORD = "nwa"  # noqa: S105 — local-only test default
DEFAULT_POSTGRES_DB = "orchestrator-core-test"


@dataclass(frozen=True)
class ServiceURIs:
    database_uri: str
    cache_uri: str


def _missing_services_message(missing: list[str]) -> str:
    return (
        f"Integration tests require {', '.join(missing)} to be available.\n"
        "Provide them in one of the following ways:\n"
        "  - Set DATABASE_URI and CACHE_URI in the environment "
        "(bring-your-own services, used by CI and the docker-compose flow).\n"
        "  - Unset both DATABASE_URI and CACHE_URI; the test runner will start\n"
        "    ephemeral Postgres+Redis containers via testcontainers, which\n"
        "    requires Docker to be running and the dev dependency group to be\n"
        "    installed (``uv sync --group dev``).\n"
        "See docs/guides/testing.md for details."
    )


def _resolve_from_env() -> ServiceURIs | None:
    db_uri = os.environ.get("DATABASE_URI")
    cache_uri = os.environ.get("CACHE_URI")
    if db_uri and cache_uri:
        return ServiceURIs(database_uri=db_uri, cache_uri=cache_uri)
    if db_uri or cache_uri:
        missing = "CACHE_URI" if not cache_uri else "DATABASE_URI"
        raise RuntimeError(
            f"Integration tests: {missing} is not set but the other service URI is.\n"
            "Set both to bring your own services, or unset both to auto-start "
            "containers via testcontainers."
        )
    return None


@contextmanager
def _testcontainers_services() -> Iterator[ServiceURIs]:
    try:
        from testcontainers.postgres import PostgresContainer
        from testcontainers.redis import RedisContainer
    except ImportError as exc:  # pragma: no cover — exercised only when extra missing
        raise RuntimeError(_missing_services_message(["Postgres", "Redis"])) from exc

    pg = PostgresContainer(
        image=DEFAULT_POSTGRES_IMAGE,
        username=DEFAULT_POSTGRES_USER,
        password=DEFAULT_POSTGRES_PASSWORD,
        dbname=DEFAULT_POSTGRES_DB,
        driver="psycopg",
    )
    redis = RedisContainer(image=DEFAULT_REDIS_IMAGE)

    try:
        pg.start()
    except Exception as exc:  # pragma: no cover — exercised only when Docker missing
        raise RuntimeError(
            "Integration tests cannot start a Postgres testcontainer.\n"
            "Either start Docker, or set DATABASE_URI and CACHE_URI to bring your own services.\n"
            f"Underlying error: {exc!r}"
        ) from exc

    try:
        redis.start()
    except Exception as exc:  # pragma: no cover
        pg.stop()
        raise RuntimeError(
            "Integration tests cannot start a Redis testcontainer.\n"
            "Either start Docker, or set DATABASE_URI and CACHE_URI to bring your own services.\n"
            f"Underlying error: {exc!r}"
        ) from exc

    try:
        db_uri = pg.get_connection_url()
        # Older versions of testcontainers report a psycopg2 URL; orchestrator uses psycopg v3.
        db_uri = db_uri.replace("postgresql+psycopg2://", "postgresql+psycopg://")
        if not db_uri.startswith("postgresql+psycopg://"):
            db_uri = db_uri.replace("postgresql://", "postgresql+psycopg://")

        cache_uri = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
        yield ServiceURIs(database_uri=db_uri, cache_uri=cache_uri)
    finally:
        redis.stop()
        pg.stop()


@contextmanager
def provide_services() -> Iterator[ServiceURIs]:
    """Yield ``ServiceURIs`` for the integration-test session.

    Resolution order: env vars -> testcontainers -> ``RuntimeError``.

    For testcontainers mode, ``DATABASE_URI`` and ``CACHE_URI`` are exported into
    ``os.environ`` before yielding so that pydantic-settings (and any
    ``orchestrator.*`` module imported later) sees the correct service
    endpoints. They are removed again on context exit if they were not already
    set when the context was entered.

    Callers that already have ``orchestrator.core.settings.app_settings``
    imported should additionally call :func:`patch_app_settings` to override
    the captured ``DATABASE_URI`` / ``CACHE_URI`` on the in-memory settings
    object. The integration conftest invokes ``provide_services`` *before* any
    ``orchestrator.*`` import so this is normally not needed, but it is
    available as a defensive helper.
    """
    env_uris = _resolve_from_env()
    if env_uris is not None:
        yield env_uris
        return

    db_was_set = "DATABASE_URI" in os.environ
    cache_was_set = "CACHE_URI" in os.environ
    with _testcontainers_services() as uris:
        os.environ["DATABASE_URI"] = uris.database_uri
        os.environ["CACHE_URI"] = uris.cache_uri
        try:
            yield uris
        finally:
            if not db_was_set:
                os.environ.pop("DATABASE_URI", None)
            if not cache_was_set:
                os.environ.pop("CACHE_URI", None)


def patch_app_settings(uris: ServiceURIs) -> None:
    """Force ``app_settings`` to point at the resolved service URIs.

    This is a defensive helper for cases where ``orchestrator.core.settings``
    has already been imported (and ``app_settings`` constructed) before
    :func:`provide_services` ran. Updating ``app_settings`` here keeps cache
    callers like ``orchestrator.core.schedules.service`` consistent with the
    environment.

    Importing this module does not import ``orchestrator``; the import is
    deferred so :func:`provide_services` can run before any ``orchestrator``
    module is loaded.
    """
    from orchestrator.core.settings import SecretPostgresDsn, SecretRedisDsn, app_settings

    app_settings.DATABASE_URI = SecretPostgresDsn(uris.database_uri)  # type: ignore[arg-type]
    app_settings.CACHE_URI = SecretRedisDsn(uris.cache_uri)  # type: ignore[arg-type]

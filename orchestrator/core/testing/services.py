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

"""Service provider for tests that need Postgres and Redis.

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

Importing any ``orchestrator.core`` module constructs ``app_settings`` and the module-level Redis clients, so they
are created before the services are resolved. :func:`patch_app_settings` points both at the resolved services.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

POSTGRES_IMAGE_ENV_VAR = "TEST_POSTGRES_IMAGE"
DEFAULT_POSTGRES_IMAGE = "pgvector/pgvector:pg17"
DEFAULT_REDIS_IMAGE = "redis:7"
DEFAULT_POSTGRES_USER = "nwa"
DEFAULT_POSTGRES_PASSWORD = "nwa"  # noqa: S105 — local-only test default
DEFAULT_POSTGRES_DB = "orchestrator-core-test"


def postgres_image() -> str:
    """The Postgres image the testcontainers fallback starts.

    Set ``TEST_POSTGRES_IMAGE`` to run the suite against another Postgres major version, for example
    ``pgvector/pgvector:pg15`` to (re)generate the ``plan_metrics/*.pg15.md`` search snapshots. The bundled
    ``docker/pytest-support/docker-compose.yaml`` honours the same variable. An unset or empty value falls back to
    :data:`DEFAULT_POSTGRES_IMAGE`.
    """
    return os.environ.get(POSTGRES_IMAGE_ENV_VAR) or DEFAULT_POSTGRES_IMAGE


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
        "    requires Docker to be running and the ``orchestrator-core[testing]``\n"
        "    extra to be installed.\n"
        "See the orchestrator-core testing guide for details."
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
        image=postgres_image(),
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


# Module-level Redis clients created from ``app_settings.CACHE_URI`` at import time: (module, attribute, is_async)
MODULE_REDIS_CLIENTS: tuple[tuple[str, str, bool], ...] = (
    ("orchestrator.core.utils.redis", "cache", False),
    ("orchestrator.core.schedules.service", "redis_connection", False),
    ("orchestrator.core.schedules.service", "redis_connection_async", True),
)


def rebind_redis_clients(cache_uri: str) -> None:
    """Replace the module-level Redis clients of already imported modules with clients for ``cache_uri``.

    Modules that are imported later create their clients from ``app_settings.CACHE_URI`` themselves.
    """
    from orchestrator.core.utils.redis_client import create_redis_asyncio_client, create_redis_client

    for module_name, attribute, is_async in MODULE_REDIS_CLIENTS:
        if module := sys.modules.get(module_name):
            factory = create_redis_asyncio_client if is_async else create_redis_client
            setattr(module, attribute, factory(cache_uri))


def patch_app_settings(uris: ServiceURIs) -> None:
    """Point ``app_settings`` and the module-level Redis clients at the resolved service URIs.

    ``app_settings`` and the Redis clients in modules like ``orchestrator.core.schedules.service`` are created when
    ``orchestrator.core`` is imported, which is before the services are resolved.
    """
    from orchestrator.core.settings import SecretPostgresDsn, SecretRedisDsn, app_settings

    app_settings.DATABASE_URI = SecretPostgresDsn(uris.database_uri)  # type: ignore[arg-type]
    app_settings.CACHE_URI = SecretRedisDsn(uris.cache_uri)  # type: ignore[arg-type]
    rebind_redis_clients(uris.cache_uri)

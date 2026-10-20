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

"""Pytest plugin with fixtures for tests that need Postgres, Redis and the orchestrator app.

Load it from the root ``conftest.py`` of your test suite::

    pytest_plugins = ["orchestrator.core.testing.fixtures"]

It is not registered automatically when ``orchestrator-core[testing]`` is installed, because the ``database``
fixture drops and recreates a database and ``db_session`` and ``fastapi_app`` are ``autouse``.

Services are resolved by :func:`orchestrator.core.testing.services.provide_services`: ``DATABASE_URI`` and
``CACHE_URI`` from the environment when both are set, otherwise ephemeral testcontainers.

Override these fixtures in your own ``conftest.py`` to adapt the plugin:

- ``alembic_config``: the alembic configuration used to migrate the test database. The default uses ``alembic.ini``
  in the current working directory when it exists, otherwise the orchestrator-core migrations.
- ``fastapi_app``: the app under test, for example to register your own routers.
- ``joined_async_session``: the async session context manager that GraphQL resolvers use.
"""

import contextlib
import os
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, ExitStack, closing, contextmanager
from copy import copy
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import close_all_sessions, sessionmaker
from starlette.testclient import TestClient
from structlog import get_logger
from urllib3_mock import Responses

from orchestrator.core.app import OrchestratorCore
from orchestrator.core.db import db, warn_db_uri_scheme, wrapped_db
from orchestrator.core.db.database import ENGINE_ARGUMENTS, SESSION_ARGUMENTS, BaseModel, Database, SearchQuery
from orchestrator.core.settings import SecretPostgresDsn, app_settings
from orchestrator.core.testing.services import ServiceURIs, patch_app_settings, provide_services
from orchestrator.core.utils.json import json_dumps

logger = get_logger(__name__)

ORCHESTRATOR_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
NO_XDIST_WORKER = "master"


def xdist_worker_id() -> str:
    """Return the pytest-xdist worker id (``gw0``, ``gw1``, ...) or ``master`` when not running distributed."""
    return os.environ.get("PYTEST_XDIST_WORKER", NO_XDIST_WORKER)


def make_db_uri(worker_id: str, base_uri: str) -> str:
    """Return a database URI that is unique per pytest-xdist worker.

    >>> make_db_uri("master", "postgresql+psycopg://nwa:nwa@localhost/orchestrator-core-test")
    'postgresql+psycopg://nwa:nwa@localhost/orchestrator-core-test'
    >>> make_db_uri("gw1", "postgresql+psycopg://nwa:nwa@localhost/orchestrator-core-test")
    'postgresql+psycopg://nwa:nwa@localhost/orchestrator-core-test-gw1'
    """
    warn_db_uri_scheme(base_uri)

    if worker_id == NO_XDIST_WORKER:
        return base_uri

    url = make_url(base_uri)
    return url.set(database=f"{url.database}-{worker_id}").render_as_string(hide_password=False)


def make_alembic_config(db_uri: str, alembic_ini: Path | None = None) -> Config:
    """Build the alembic configuration that migrates the database at ``db_uri``.

    Args:
        db_uri: The database to migrate.
        alembic_ini: The ``alembic.ini`` of your orchestrator. Its ``version_locations`` are extended with the
            orchestrator-core migrations, like the ``db`` CLI commands do. When omitted, only the orchestrator-core
            migrations are used.

    Returns:
        The alembic configuration.
    """
    core_versions = ORCHESTRATOR_MIGRATIONS_DIR / "versions" / "schema"
    if alembic_ini is None:
        cfg = Config(file_=str(ORCHESTRATOR_MIGRATIONS_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(ORCHESTRATOR_MIGRATIONS_DIR))
        cfg.set_main_option("version_locations", str(core_versions))
    else:
        cfg = Config(file_=str(alembic_ini))
        version_locations = cfg.get_main_option("version_locations")
        cfg.set_main_option("version_locations", f"{version_locations} {core_versions}")
    cfg.set_main_option("sqlalchemy.url", db_uri)
    return cfg


def run_migrations(db_uri: str, alembic_cfg: Config | None = None) -> None:
    """Migrate the database at ``db_uri`` to the latest revision of all heads.

    Args:
        db_uri: The database to migrate.
        alembic_cfg: The alembic configuration to use. Defaults to the orchestrator-core migrations.
    """
    os.environ["DATABASE_URI"] = db_uri
    app_settings.DATABASE_URI = SecretPostgresDsn(db_uri)  # type: ignore[arg-type]
    command.upgrade(alembic_cfg or make_alembic_config(db_uri), "heads")


class JsonTestClient(TestClient):
    """Starlette test client that serializes ``json=`` with the orchestrator JSON encoder (UUIDs, datetimes, ...)."""

    def request(
        self,
        method: str,
        url: httpx._types.URLTypes,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        json: Any = None,
        **kwargs: Any,
    ) -> httpx.Response:
        if json is None:
            return super().request(method, url, data=data, headers=headers, **kwargs)

        json_headers = {**(headers or {}), "Content-Type": "application/json"}
        return super().request(method, url, data=json_dumps(json).encode(), headers=json_headers, **kwargs)  # type: ignore[arg-type]


@contextmanager
def make_orchestrator_app() -> Iterator[OrchestratorCore]:
    """Create an ``OrchestratorCore`` app for tests, with OAuth2 disabled and ``ENVIRONMENT=TESTING``."""
    from oauth2_lib.settings import oauth2lib_settings
    from orchestrator.core.forms.scheduler_form import configure_schedule_form
    from pydantic_forms.core.shared import register_form

    register_form("configure_schedule", configure_schedule_form)

    with (
        patch.multiple(
            oauth2lib_settings,
            OAUTH2_ACTIVE=False,
            ENVIRONMENT_IGNORE_MUTATION_DISABLED=["local", "TESTING"],
        ),
        patch.multiple(
            app_settings,
            ENABLE_PROMETHEUS_METRICS_ENDPOINT=True,
            ENVIRONMENT="TESTING",
        ),
    ):
        app = OrchestratorCore(base_settings=app_settings)
        if app.broadcast_thread:
            app.broadcast_thread.start()

        try:
            yield app
        finally:
            app.worker_status_monitor.stop()
            if app.broadcast_thread:
                app.broadcast_thread.stop()


def _wrapped_database() -> Database:
    if not isinstance(test_database := wrapped_db.wrapped_database, Database):
        raise RuntimeError("No database configured, use the `database` fixture")  # noqa: TRY003
    return test_database


@contextlib.asynccontextmanager
async def session_joined_async() -> AsyncIterator[AsyncSession]:
    """AsyncSession bound to the per-test transaction opened by ``db_session``.

    ``db.async_session()`` uses the async engine's own connection pool, so its commits are real
    and escape ``db_session``'s rollback, leaking into later tests. Binding an ``AsyncConnection``
    to the already-open sync test connection and joining it via a savepoint keeps this session's
    work inside that same outer transaction, so it rolls back with everything else.
    """
    async_connection = AsyncConnection(_wrapped_database().async_engine, sync_connection=db.session.connection())
    async with AsyncSession(
        bind=async_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


@pytest.fixture(scope="session")
def integration_services() -> Iterator[ServiceURIs]:
    """Resolve Postgres and Redis for the test session, from the environment or testcontainers."""
    with ExitStack() as stack:
        uris = stack.enter_context(provide_services())
        patch_app_settings(uris)
        yield uris


@pytest.fixture(scope="session")
def db_uri(integration_services: ServiceURIs) -> Iterator[str]:
    """The URI of the test database, with a suffix per pytest-xdist worker so workers do not share a database."""
    session_db_uri = make_db_uri(xdist_worker_id(), integration_services.database_uri)

    with patch.object(app_settings, "DATABASE_URI", SecretPostgresDsn(session_db_uri)):  # type: ignore[arg-type]
        yield session_db_uri


@pytest.fixture(scope="session")
def alembic_config(db_uri: str) -> Config:
    """Alembic configuration used to migrate the test database.

    Uses ``alembic.ini`` in the current working directory when present, otherwise the orchestrator-core migrations.
    Override this fixture to point at another configuration.
    """
    alembic_ini = Path.cwd() / "alembic.ini"
    return make_alembic_config(db_uri, alembic_ini if alembic_ini.is_file() else None)


@pytest.fixture(scope="session")
def database(db_uri: str, alembic_config: Config) -> Iterator[None]:
    """Create the test database, run the migrations, and drop the database at the end of the session."""
    wrapped_db.update(Database(db_uri))
    url = make_url(db_uri)
    db_to_create = url.database
    engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with closing(engine.connect()) as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_to_create}";'))
        conn.execute(
            text(f'CREATE DATABASE "{db_to_create}" LOCALE_PROVIDER icu ICU_LOCALE "en-US" TEMPLATE template0;')
        )

    run_migrations(db_uri, alembic_config)
    test_database = _wrapped_database()
    test_database.engine = create_engine(db_uri, **ENGINE_ARGUMENTS)

    try:
        yield
    finally:
        test_database.engine.dispose()
        close_all_sessions()

        with closing(engine.connect()) as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid)"
                    " FROM pg_stat_activity"
                    " WHERE datname = :dbname"
                    " AND pid <> pg_backend_pid()"
                ),
                {"dbname": db_to_create},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_to_create}";'))


@pytest.fixture(autouse=True)
def db_session(database: None) -> Iterator[None]:
    """Run each test in a transaction that is rolled back afterwards.

    Commits made by the code under test are tied to an outer transaction on the test connection. They are visible
    to queries within the test, and rolled back when the test ends, leaving the database as the migrations left it.
    """
    test_database = _wrapped_database()
    with closing(test_database.engine.connect()) as test_connection:
        test_database.session_factory = sessionmaker(bind=test_connection, **SESSION_ARGUMENTS)  # type: ignore[call-overload]
        test_database.scoped_session = scoped_session(test_database.session_factory, test_database._scopefunc)
        BaseModel.set_query(cast(SearchQuery, test_database.scoped_session.query_property()))

        trans = test_connection.begin()
        try:
            yield
        finally:
            try:
                close_all_sessions()
            except Exception:
                logger.exception("Closing wrapped db connections failed, test teardown may fail")
            if not trans._deactivated_from_connection:
                trans.rollback()


@pytest.fixture(autouse=True)
def responses(request: pytest.FixtureRequest) -> Iterator[Responses | None]:
    """Mock outgoing HTTP calls made with ``requests``. Mark a test with ``noresponses`` to disable mocking."""
    if request.node.get_closest_marker("noresponses"):
        yield None
        return
    responses_mock = Responses("requests.packages.urllib3")
    with responses_mock:
        yield responses_mock


@pytest.fixture(scope="session", autouse=True)
def fastapi_app(database: None, db_uri: str) -> Iterator[OrchestratorCore]:
    """The orchestrator app under test. Override it to customize the app."""
    with make_orchestrator_app() as app:
        yield app


@pytest.fixture
def fastapi_app_graphql(fastapi_app: OrchestratorCore) -> Iterator[OrchestratorCore]:
    """The session app with the GraphQL router (re)registered, so it reflects the product models of this test."""
    original_routes = copy(fastapi_app.router.routes)
    original_router = fastapi_app.graphql_router

    fastapi_app.register_graphql()

    yield fastapi_app

    fastapi_app.router.routes = original_routes
    fastapi_app.graphql_router = original_router


@pytest.fixture(scope="session")
def test_client(fastapi_app: OrchestratorCore) -> JsonTestClient:
    """Client to test REST calls."""
    return JsonTestClient(fastapi_app)


@pytest.fixture(scope="session")
def joined_async_session() -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    """Factory for async sessions that join the per-test transaction. See :func:`session_joined_async`."""
    return session_joined_async


@pytest.fixture
def test_client_graphql(
    fastapi_app_graphql: OrchestratorCore,
    db_session: None,
    joined_async_session: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> Iterator[JsonTestClient]:
    """Client to test GraphQL queries.

    GraphQL resolvers call ``db.async_session()`` directly. It is patched so they use the per-test transaction
    opened by ``db_session``.
    """
    original = db.async_session
    db.async_session = joined_async_session  # type: ignore[method-assign,assignment]
    try:
        yield JsonTestClient(fastapi_app_graphql)
    finally:
        db.async_session = original  # type: ignore[method-assign]

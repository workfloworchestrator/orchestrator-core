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

"""What the API answers when the database connection pool is exhausted.

A pool is exhausted by swapping in one with a single connection and holding it checked out for the test, so the
responses come from the real middlewares, routes, exception handlers and GraphQL schema. ``db_session`` keeps the
test's own sessions on a separate connection, so this does not break the rest of the session.
"""

import asyncio
from http import HTTPStatus

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.util import greenlet_spawn
from starlette.testclient import TestClient

from orchestrator.core.db import db
from orchestrator.core.exception_handlers import DATABASE_UNAVAILABLE_MESSAGE
from orchestrator.core.testing.fixtures import JsonTestClient

POOL_TIMEOUT = 0.2

REST_ENDPOINT = "/api/health/"  # The one REST endpoint that queries through the async engine.
GRAPHQL_QUERY = "{ subscriptions(first: 1) { pageInfo { totalItems } } }"


def _single_connection_pool(creator) -> QueuePool:
    return QueuePool(creator=creator, timeout=POOL_TIMEOUT, pool_size=1, max_overflow=0)


@pytest.fixture
def exhausted_sync_pool():
    """Exhaust the pool behind the scoped sync session, which most REST endpoints and workflows use."""
    wrapped_database = db.wrapped_database
    original_pool = wrapped_database.engine.pool
    original_session_factory = wrapped_database.session_factory
    original_scoped_session = wrapped_database.scoped_session

    # The per-test session factory is bound to a Connection; bind this one to the engine so requests use its pool.
    replacement_pool = _single_connection_pool(original_pool._creator)
    wrapped_database.engine.pool = replacement_pool
    wrapped_database.session_factory = sessionmaker(
        bind=wrapped_database.engine,
        class_=original_session_factory.class_,
        autoflush=True,
    )
    wrapped_database.scoped_session = scoped_session(wrapped_database.session_factory, wrapped_database._scopefunc)
    held_connection = wrapped_database.engine.connect()
    try:
        yield
    finally:
        held_connection.close()
        wrapped_database.session_factory = original_session_factory
        wrapped_database.scoped_session = original_scoped_session
        wrapped_database.engine.pool = original_pool
        replacement_pool.dispose()


@pytest.fixture
def exhausted_async_pool():
    """Exhaust the pool behind ``get_async_session``, which the async REST endpoints use.

    The connection is checked out through the engine's sync face, inside a greenlet. ``AsyncEngine.connect()`` is not a
    coroutine function: it returns the ``AsyncConnection`` immediately and only acquires a pooled connection when that
    object is started, so ``asyncio.run(db.async_engine.connect())`` gets an ``AsyncConnection`` where it expects a
    coroutine. The connection an async dialect hands out also has to be released from inside the greenlet that checked
    it out, so teardown closes it the same way.
    """

    async def _checkout() -> Connection:
        return await greenlet_spawn(db.async_engine.sync_engine.connect)

    async def _release(connection: Connection) -> None:
        await greenlet_spawn(connection.close)

    original_pool = db.async_engine.pool
    replacement_pool = _single_connection_pool(original_pool._creator)
    db.async_engine.pool = replacement_pool
    held_connection = asyncio.run(_checkout())
    try:
        yield
    finally:
        asyncio.run(_release(held_connection))
        db.async_engine.pool = original_pool
        replacement_pool.dispose()


@pytest.fixture
def client(fastapi_app) -> TestClient:
    """A client without the ``test_client`` rerouting of the async session to the per-test transaction."""
    return JsonTestClient(fastapi_app)


@pytest.fixture
def client_graphql(fastapi_app_graphql) -> TestClient:
    return JsonTestClient(fastapi_app_graphql)


# --- REST ---


def test_async_endpoint_returns_503_when_the_pool_is_exhausted(client: TestClient, exhausted_async_pool: None) -> None:
    response = client.get(REST_ENDPOINT)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": DATABASE_UNAVAILABLE_MESSAGE,
        "status": HTTPStatus.SERVICE_UNAVAILABLE.value,
        "title": HTTPStatus.SERVICE_UNAVAILABLE.phrase,
    }
    assert response.headers["Retry-After"] == "5"


def test_scoped_session_returns_503_when_the_pool_is_exhausted(
    client: TestClient, fastapi_app, exhausted_sync_pool: None
) -> None:
    def use_the_scoped_session():
        db.session.execute(text("SELECT 1"))
        return "ok"

    fastapi_app.add_api_route("/_pool_test", use_the_scoped_session, methods=["GET"])

    response = client.get("/_pool_test")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_the_endpoint_answers_normally_when_the_pool_has_room(client: TestClient) -> None:
    assert client.get(REST_ENDPOINT).status_code == HTTPStatus.OK


# --- GraphQL ---


def test_graphql_returns_the_timeout_as_an_error_not_a_503(
    client_graphql: TestClient, exhausted_sync_pool: None
) -> None:
    """GraphQL keeps its 200 + ``errors`` shape; a resolver cannot answer with a 503."""
    response = client_graphql.post("/api/graphql", json={"query": GRAPHQL_QUERY})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["data"] is None
    errors = response.json()["errors"]
    assert len(errors) == 1
    assert errors[0]["path"] == ["subscriptions"]
    # Without DEBUG the error handler extension hides the details of internal errors.
    assert errors[0]["message"] == "Internal Server Error"


def test_graphql_answers_normally_when_the_pool_has_room(client_graphql: TestClient) -> None:
    response = client_graphql.post("/api/graphql", json={"query": GRAPHQL_QUERY})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": {"subscriptions": {"pageInfo": {"totalItems": 0}}}}

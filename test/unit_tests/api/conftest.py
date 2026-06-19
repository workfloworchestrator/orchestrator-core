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

"""Fixtures for unit-testing FastAPI endpoints without a real database.

``fastapi_app`` creates an ``OrchestratorCore`` with two things mocked:
- ``init_database`` is patched out so no SQLAlchemy engine is created and no
  Postgres connection is attempted.
- ``db.database_scope`` is patched with a no-op context manager so that
  ``DBSessionMiddleware`` can handle requests without a live session factory.

Tests that make HTTP requests additionally override the ``get_async_session``
FastAPI dependency via ``test_client``, supplying a per-test ``AsyncMock``
session they can configure freely.
"""

from contextlib import contextmanager
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from orchestrator.core.app import OrchestratorCore
from orchestrator.core.db import get_async_session


@contextmanager
def _noop_database_scope(**kwargs):  # type: ignore[misc]
    yield


@pytest.fixture(scope="module")
def fastapi_app():
    from orchestrator.core.db import db as orchestrator_db

    with (
        patch("orchestrator.core.app.init_database"),
        patch.object(orchestrator_db, "database_scope", _noop_database_scope),
    ):
        yield OrchestratorCore()


@pytest.fixture
def mock_async_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def test_client(fastapi_app, mock_async_session: AsyncMock):
    async def _override() -> AsyncIterator[AsyncSession]:
        yield mock_async_session

    fastapi_app.dependency_overrides[get_async_session] = _override
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.pop(get_async_session, None)

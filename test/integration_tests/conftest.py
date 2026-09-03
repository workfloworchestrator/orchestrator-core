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

"""Integration-test conftest shim.

Fixtures, hooks, and helpers live in :mod:`test.integration_tests._fixtures`
so sibling trees (e.g. ``test/acceptance_tests/celery``) can load them via
``pytest_plugins`` without the dual-registration error pluggy raises when
the same module is path-discovered AND named as a plugin.
"""

pytest_plugins = ["test.integration_tests._fixtures"]

# Re-export non-fixture symbols (constants, classes, plain helpers) that
# individual test files import by name. Fixtures and hooks are NOT
# re-exported — they reach tests through the plugin loaded above.
from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from orchestrator.core.db import get_async_session  # noqa: E402
from test.integration_tests._async_session import session_joined_async  # noqa: E402
from test.integration_tests._fixtures import (  # noqa: E402
    CUSTOMER_ID,
    JsonTestClient,
    TestOrchestratorCelery,
    do_refresh_subscriptions_search_view,
)

__all__ = [
    "CUSTOMER_ID",
    "TestOrchestratorCelery",
    "do_refresh_subscriptions_search_view",
]


@pytest.fixture(autouse=True)
def test_client(fastapi_app, db_session):
    """Test client whose async endpoints share the per-test transaction.

    The endpoints below depend on ``get_async_session``, which opens a connection on the async
    engine's own pool; that cannot see the uncommitted rows the async fixtures stage on the sync
    test connection.
    """

    async def _override_async() -> AsyncIterator[AsyncSession]:
        async with session_joined_async() as session:
            yield session

    fastapi_app.dependency_overrides[get_async_session] = _override_async
    try:
        yield JsonTestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture()
async def async_session(fastapi_app, db_session):
    """Test client whose async endpoints share the per-test transaction.

    The endpoints below depend on ``get_async_session``, which opens a connection on the async
    engine's own pool; that cannot see the uncommitted rows the async fixtures stage on the sync
    test connection.
    """

    async with session_joined_async() as session:
        yield session

# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

import pytest

from test.integration_tests._async_session import session_joined_async
from test.integration_tests.search.performance.conftest import db_session, sorted_gist_build  # noqa: F401

# The database with Alembic migrations, app and session, plus this repo's own integration fixtures on top of them, loaded
# as the integration and acceptance tests do.
pytest_plugins = ["orchestrator.core.testing.fixtures", "test.integration_tests._fixtures"]

pytestmark = pytest.mark.search


@pytest.fixture
async def async_session(db_session):  # noqa: F811
    """An async session joined to the per-test transaction, as the integration tests' `async_session`."""
    async with session_joined_async() as session:
        yield session

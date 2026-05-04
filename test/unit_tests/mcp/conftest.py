# Copyright 2019-2026 ESnet.
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

"""Conftest for MCP unit tests.

Overrides the session-level autouse fixtures from the root conftest that
require a live PostgreSQL connection.  The MCP auth tests are pure unit
tests that mock all I/O; they do not need a database.
"""

import pytest


@pytest.fixture(autouse=True)
def db_session():
    """No-op override: MCP unit tests do not need a database transaction."""
    yield


@pytest.fixture(scope="session", autouse=True)
def fastapi_app():
    """No-op override: MCP unit tests do not need the full OrchestratorCore app."""
    yield None


@pytest.fixture(autouse=True)
def responses():
    """No-op override: MCP unit tests do not use urllib3 response mocking."""
    yield None


@pytest.fixture(scope="session", autouse=True)
def test_form_translations():
    """No-op override: MCP unit tests do not exercise form translation checks."""
    yield

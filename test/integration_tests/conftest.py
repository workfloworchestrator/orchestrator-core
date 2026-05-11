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
from test.integration_tests._fixtures import (  # noqa: E402
    CUSTOMER_ID,
    TestOrchestratorCelery,
    do_refresh_subscriptions_search_view,
)

__all__ = [
    "CUSTOMER_ID",
    "TestOrchestratorCelery",
    "do_refresh_subscriptions_search_view",
]

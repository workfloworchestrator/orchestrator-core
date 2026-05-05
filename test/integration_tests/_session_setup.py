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

"""Session prelude for integration tests.

This module is imported from ``test/integration_tests/conftest.py`` *before*
any ``orchestrator.*`` import. Resolving services here (env vars first,
testcontainers fallback) ensures that:

- ``DATABASE_URI`` and ``CACHE_URI`` are present in ``os.environ`` before
  pydantic-settings constructs ``app_settings``;
- module-level cache clients in ``orchestrator.core.schedules.service`` and
  ``orchestrator.core.utils.redis`` bind to the right Redis instance.

Cleanup is handled by ``pytest_sessionfinish`` in the conftest.
"""

from __future__ import annotations

from contextlib import ExitStack

from test.integration_tests.fixtures.services import ServiceURIs, provide_services

SERVICES_STACK = ExitStack()
SERVICES: ServiceURIs = SERVICES_STACK.enter_context(provide_services())

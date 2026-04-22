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

from unittest.mock import patch

from dirty_equals import IsFloat, IsInt

from orchestrator.core.db.listeners import disable_listeners, monitor_sqlalchemy_queries
from orchestrator.core.settings import app_settings
from test.unit_tests.config import GRAPHQL_ENDPOINT


def test_stats_extension(fastapi_app_graphql, test_client_graphql):
    # given
    query = """query MyQuery {
      workflows(first: 10) {
        page {
          name
        }
      }
    }"""
    try:
        monitor_sqlalchemy_queries()
        with patch.object(app_settings, "ENABLE_GRAPHQL_STATS_EXTENSION", True):
            fastapi_app_graphql.register_graphql()

            # when
            response = test_client_graphql.post(GRAPHQL_ENDPOINT, json={"query": query})
    finally:
        disable_listeners()

    # then
    result = response.json()
    assert result["extensions"]["stats"] == {"db_queries": IsInt, "db_time": IsFloat, "operation_time": IsFloat}

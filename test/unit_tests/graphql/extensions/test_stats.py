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

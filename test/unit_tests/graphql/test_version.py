import json
from http import HTTPStatus

from test.unit_tests.config import GRAPHQL_ENDPOINT


def get_version_query() -> bytes:
    query = """
        query VersionQuery {
        version {
            applicationVersions
        }
        }
    """
    return json.dumps({"operationName": "VersionQuery", "query": query}).encode("utf-8")


def test_version_query(test_client_graphql):
    data = get_version_query()
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers={"Content-Type": "application/json"})
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result

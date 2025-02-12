import json
from http import HTTPStatus


def get_workflows_query() -> bytes:
    query = """
        query VersionQuery {
        version {
            applicationVersions
        }
        }
    """
    return json.dumps(
        {
            "operationName": "VersionQuery",
            "query": query
        }
    ).encode("utf-8")


def test_workflows_query(test_client):
    data = get_workflows_query(first=2)
    response = test_client.get("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    assert "errors" not in result

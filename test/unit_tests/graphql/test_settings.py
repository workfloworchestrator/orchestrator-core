import json
from http import HTTPStatus


def get_settings_query() -> bytes:
    query = """
query SettingsQuery {
  settings {
    cacheNames
    engineSettings {
      globalLock
      globalStatus
      runningProcesses
    }
    workerStatus {
      executorType
      numberOfQueuedJobs
      numberOfWorkersOnline
      numberOfRunningJobs
    }
  }
}
    """
    return bytes(json.dumps({"operationName": "SettingsQuery", "query": query}), "utf-8")


def get_clear_cache_mutation(name: str = "all"):
    query = """
mutation ClearCacheMutation($name: String!) {
  clearCache(name: $name) {
    __typename
    ... on CacheClearSuccess {
      deleted
    }
    ... on Error {
      message
    }
  }
}
    """
    return json.dumps({"operationName": "ClearCacheMutation", "query": query, "variables": {"name": name}}).encode(
        "utf-8"
    )


def test_settings_query(test_client):
    response = test_client.post(
        "/api/graphql",
        content=get_settings_query(),
        headers={"Content-Type": "application/json"},
    )
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    settings_data = result["data"]["settings"]

    assert settings_data == {
        "cacheNames": {"all": "All caches"},
        "engineSettings": {"globalLock": False, "globalStatus": "RUNNING", "runningProcesses": 0},
        "workerStatus": {
            "executorType": "threadpool",
            "numberOfQueuedJobs": 0,
            "numberOfWorkersOnline": 5,
            "numberOfRunningJobs": 1,
        },
    }


def test_clear_cache_mutation_fails_auth(test_client):
    data = get_clear_cache_mutation()
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert response.status_code == HTTPStatus.OK
    result = response.json()

    # TODO: Fix oauth2_lib or override default MUTATIONS_ENABLED & OAUTH2_ACTIVE
    # and create fake OIDC user for requests...
    assert result["data"] is None
    assert result["errors"][0]["message"] == "User is not authenticated"

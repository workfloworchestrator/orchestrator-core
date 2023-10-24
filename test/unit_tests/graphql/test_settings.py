import json
from hashlib import md5
from http import HTTPStatus

from redis import Redis

from orchestrator import app_settings
from orchestrator.utils.redis import ONE_WEEK
from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


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


def get_test_set_global_lock_mutation(global_lock: bool = False):
    query = """
mutation UpdateStatusMutation($globalLock: Boolean = false) {
  updateStatus(globalLock: $globalLock) {
    __typename
    ... on EngineSettingsType {
      globalStatus
      globalLock
      runningProcesses
    }
    ... on Error {
      message
    }
  }
}
    """
    return json.dumps(
        {"operationName": "UpdateStatusMutation", "query": query, "variables": {"globalLock": global_lock}}
    ).encode("utf-8")


def test_settings_query(test_client):
    response = test_client.post(
        GRAPHQL_ENDPOINT,
        content=get_settings_query(),
        headers=GRAPHQL_HEADERS,
    )
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    settings_data = result["data"]["settings"]
    worker_status = settings_data["workerStatus"]

    assert settings_data["cacheNames"] == {"all": "All caches"}
    assert settings_data["engineSettings"] == {"globalLock": False, "globalStatus": "RUNNING", "runningProcesses": 0}
    assert worker_status["executorType"] == "threadpool"
    assert worker_status["numberOfQueuedJobs"] == 0
    assert worker_status["numberOfWorkersOnline"] == 5
    # numberOfRunningJobs is different depending if you run the whole suite vs just the graphql tests


def test_clear_cache_mutation_fails_auth(test_client, monkeypatch):
    from oauth2_lib.settings import oauth2lib_settings

    monkeypatch.setattr(oauth2lib_settings, "ENVIRONMENT_IGNORE_MUTATION_DISABLED", [])

    # oauth2lib_settings.ENVIRONMENT_IGNORE_MUTATION_DISABLED = []
    data = get_clear_cache_mutation()
    response = test_client.post("/api/graphql", content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()

    assert result["data"] is None
    assert result["errors"][0]["message"] == "User is not authenticated"


def test_success_clear_cache(test_client, cache_fixture):
    cache = Redis.from_url(str(app_settings.CACHE_URI))
    key = "some_model_uuid"
    test_data = {key: {"data": [1, 2, 3]}}

    # Add test data to cache
    cache.set(f"orchestrator:{key}", json.dumps(test_data), ex=ONE_WEEK)
    cache.set(
        f"orchestrator:etag:{key}",
        md5(json.dumps(test_data).encode("utf-8"), usedforsecurity=False).hexdigest(),  # noqa: S303
        ex=ONE_WEEK,
    )
    cache_fixture.extend([f"orchestrator:{key}", f"orchestrator:etag:{key}"])

    assert len(cache.keys()) == 2

    response = test_client.post("/api/graphql", content=get_clear_cache_mutation(), headers=GRAPHQL_HEADERS)
    assert HTTPStatus.OK == response.status_code

    result = response.json()
    data = result["data"]["clearCache"]
    assert data["__typename"] == "CacheClearSuccess"
    assert len(cache.keys()) == 0
    assert data["deleted"] == 2


def test_failure_clear_cache(test_client):
    response = test_client.post(GRAPHQL_ENDPOINT, content=get_clear_cache_mutation("invalid"), headers=GRAPHQL_HEADERS)
    assert HTTPStatus.OK == response.status_code
    result = response.json()

    assert result["data"] == {"clearCache": {"__typename": "Error", "message": "Invalid cache name"}}


def test_mutate_engine_global_settings(test_client):
    # Turn it off
    response = test_client.post(
        GRAPHQL_ENDPOINT, content=get_test_set_global_lock_mutation(True), headers=GRAPHQL_HEADERS
    )
    assert HTTPStatus.OK == response.status_code

    result = response.json()

    status_data = result["data"]["updateStatus"]
    assert status_data["__typename"] == "EngineSettingsType"
    assert status_data["globalStatus"] == "PAUSED"
    assert status_data["globalLock"] is True

    # Turn it back on
    response = test_client.post(
        GRAPHQL_ENDPOINT, content=get_test_set_global_lock_mutation(False), headers=GRAPHQL_HEADERS
    )
    assert HTTPStatus.OK == response.status_code

    result = response.json()

    status_data = result["data"]["updateStatus"]
    assert status_data["__typename"] == "EngineSettingsType"
    assert status_data["globalStatus"] == "RUNNING"
    assert status_data["globalLock"] is False

from http import HTTPStatus
from unittest import mock
from unittest.mock import AsyncMock, Mock, patch

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy.exc import SQLAlchemyError

from orchestrator.core.db import db
from orchestrator.core.services.settings import get_engine_settings_table
from orchestrator.core.services.settings_env_variables import expose_settings, get_all_exposed_settings


def test_get_engine_status(test_client):
    engine_settings = get_engine_settings_table()
    response = test_client.get("/api/settings/status")
    assert response.status_code == HTTPStatus.OK
    # Worker-based counting: no actual workers executing in test environment
    assert response.json()["running_processes"] == 0
    assert response.json()["global_lock"] is False
    assert response.json()["global_status"] == "RUNNING"

    # Set global lock - count should still be 0 (no workers executing)
    engine_settings.global_lock = True
    db.session.flush()

    response = test_client.get("/api/settings/status")
    assert response.status_code == HTTPStatus.OK
    # Worker-based counting: still 0 as no actual workers are executing
    assert response.json()["running_processes"] == 0
    assert response.json()["global_lock"] is True
    assert response.json()["global_status"] == "PAUSED"


def test_set_engine_status(test_client):
    response = test_client.put("/api/settings/status", json={"global_lock": True})
    assert response.status_code == HTTPStatus.OK
    assert response.json()["running_processes"] == 0
    assert response.json()["global_lock"] is True
    assert response.json()["global_status"] == "PAUSED"

    response = test_client.put("/api/settings/status", json={"global_lock": False})
    assert response.status_code == HTTPStatus.OK
    assert response.json()["running_processes"] == 0
    assert response.json()["global_lock"] is False
    assert response.json()["global_status"] == "RUNNING"


def test_reset_search_index(test_client, generic_subscription_1, generic_subscription_2):
    # Initially no subscriptions found in index
    response = test_client.get("/api/subscriptions/search?query=status:active")
    assert response.status_code == HTTPStatus.OK
    subscriptions = response.json()
    assert len(subscriptions) == 0

    # Refresh index
    response = test_client.post("/api/settings/search-index/reset")
    assert response.status_code == HTTPStatus.OK

    # Subscriptions are now found
    response = test_client.get("/api/subscriptions/search?query=status:active")
    subscriptions = response.json()

    assert len(subscriptions) == 2


def test_reset_search_index_error(test_client, generic_subscription_1, generic_subscription_2):
    with mock.patch.object(db, "session") as ex:
        session_execute_mock = Mock(side_effect=SQLAlchemyError("Database error"))
        ex.attach_mock(session_execute_mock, "execute")
        response = test_client.post("/api/settings/search-index/reset")
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_get_exposed_settings(test_client):
    class MySettings(BaseSettings):
        db_password: SecretStr = "test_password"  # noqa: S105

    my_settings = MySettings()
    expose_settings("my_settings", my_settings)
    assert len(get_all_exposed_settings()) == 1

    response = test_client.get("/api/settings/overview")
    assert response.status_code == HTTPStatus.OK

    exposed_settings = response.json()

    # Find the env_name db_password and ensure it is masked is **********
    session_secret = next((var for var in exposed_settings[0]["variables"] if var["env_name"] == "db_password"), None)
    assert session_secret is not None
    assert session_secret["env_value"] == "**********"


def test_get_cache_names(test_client):
    response = test_client.get("/api/settings/cache-names")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert isinstance(data, dict)
    assert "all" in data


def test_clear_cache_invalid_name(test_client):
    with patch("orchestrator.core.api.api_v1.endpoints.settings.create_redis_asyncio_client") as mock_redis:
        mock_redis.return_value = AsyncMock()
        response = test_client.delete("/api/settings/cache/invalid")
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_get_worker_status_threadpool(test_client):
    response = test_client.get("/api/settings/worker-status")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert "executor_type" in data
    assert "number_of_workers_online" in data
    assert "number_of_queued_jobs" in data
    assert "number_of_running_jobs" in data

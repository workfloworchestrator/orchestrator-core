from http import HTTPStatus

from orchestrator.db import db
from orchestrator.services.settings import get_engine_settings


def test_get_engine_status(test_client):
    engine_settings = get_engine_settings()
    response = test_client.get("/api/settings/status")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["running_processes"] == 0
    assert response.json()["global_lock"] is False
    assert response.json()["global_status"] == "RUNNING"

    engine_settings.global_lock = True
    engine_settings.running_processes = 1
    db.session.flush()

    response = test_client.get("/api/settings/status")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["running_processes"] == 1
    assert response.json()["global_lock"] is True
    assert response.json()["global_status"] == "PAUSING"

    engine_settings.running_processes = 0
    db.session.flush()

    response = test_client.get("/api/settings/status")
    assert response.status_code == HTTPStatus.OK
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

from http import HTTPStatus
from unittest.mock import patch
from uuid import uuid4


@patch("orchestrator.api.api_v1.endpoints.schedules.add_scheduled_task_to_queue")
def test_create_scheduled_task(mock_add, test_client):
    body = {
        "name": "Test Job",
        "workflow_name": "wf",
        "workflow_id": str(uuid4()),
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 30},
    }

    response = test_client.post("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.CREATED
    assert response.json() == {
        "message": "Added to Create Queue",
        "status": "CREATED",
    }

    mock_add.assert_called_once()


@patch("orchestrator.api.api_v1.endpoints.schedules.add_scheduled_task_to_queue")
def test_update_scheduled_task(mock_add, test_client):
    body = {
        "schedule_id": str(uuid4()),
        "name": "Updated Name",
        "workflow_name": "wf",
        "workflow_id": str(uuid4()),
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 10},
    }

    response = test_client.put("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "message": "Added to Update Queue",
        "status": "UPDATED",
    }

    mock_add.assert_called_once()


@patch("orchestrator.api.api_v1.endpoints.schedules.add_scheduled_task_to_queue")
def test_delete_scheduled_task(mock_add, test_client):
    body = {
        "schedule_id": str(uuid4()),
        "workflow_id": str(uuid4()),
        "name": None,
        "trigger": None,
        "trigger_kwargs": None,
    }

    response = test_client.request("DELETE", "/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "message": "Added to Delete Queue",
        "status": "DELETED",
    }

    mock_add.assert_called_once()

"""Tests for schedules API: create, update, delete scheduled tasks with authorization checks."""

from http import HTTPStatus
from unittest.mock import patch
from uuid import uuid4

from inline_snapshot import snapshot

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.core.db.models import WorkflowApschedulerJob, WorkflowTable
from orchestrator.core.targets import Target
from orchestrator.core.workflow import done, init, workflow
from test.unit_tests.workflows import WorkflowInstanceForTests


async def _allow(_: OIDCUserModel | None = None) -> bool:
    return True


async def _disallow(_: OIDCUserModel | None = None) -> bool:
    return False


@patch("orchestrator.api.api_v1.endpoints.schedules.add_scheduled_task_to_queue")
def test_create_scheduled_task(mock_add, test_client):
    @workflow(target=Target.SYSTEM, authorize_callback=_allow)
    def create_task_wf():
        return init >> done

    body = {
        "name": "Test Job",
        "workflow_name": "create_task_wf",
        "workflow_id": str(uuid4()),
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 30},
    }

    with WorkflowInstanceForTests(create_task_wf, "create_task_wf"):
        response = test_client.post("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.CREATED
    assert response.json() == snapshot(
        {
            "message": "Added to Create Queue",
            "status": "CREATED",
        }
    )
    mock_add.assert_called_once()


def test_create_scheduled_task_not_found(test_client):
    body = {
        "name": "Test Job",
        "workflow_name": "not found",
        "workflow_id": str(uuid4()),
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 30},
    }

    response = test_client.post("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == snapshot({"detail": "Task does not exist", "status": 404, "title": "Not Found"})


def test_create_scheduled_task_unauthorized(test_client):
    @workflow(target=Target.SYSTEM, authorize_callback=_disallow)
    def unauthorized_create_wf():
        return init >> done

    body = {
        "name": "Test Job",
        "workflow_name": "unauthorized_create_wf",
        "workflow_id": str(uuid4()),
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 30},
    }

    with WorkflowInstanceForTests(unauthorized_create_wf, "unauthorized_create_wf"):
        response = test_client.post("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == snapshot(
        {
            "detail": "User is not authorized to manage schedule with 'unauthorized_create_wf' task",
            "status": 403,
            "title": "Forbidden",
        }
    )


@patch("orchestrator.api.api_v1.endpoints.schedules.add_scheduled_task_to_queue")
@patch("orchestrator.api.api_v1.endpoints.schedules.get_workflow_by_workflow_id")
@patch("orchestrator.api.api_v1.endpoints.schedules.get_linker_entries_by_schedule_ids")
def test_update_scheduled_task(
    mock_get_linker_entries_by_schedule_ids, mock_get_workflow_by_workflow_id, mock_add, test_client
):
    @workflow(target=Target.SYSTEM, authorize_callback=_allow)
    def update_task_wf():
        return init >> done

    body = {
        "schedule_id": str(uuid4()),
        "name": "Updated Name",
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 10},
    }

    mock_get_linker_entries_by_schedule_ids.return_value = [
        WorkflowApschedulerJob(schedule_id=body["schedule_id"], workflow_id=str(uuid4()))
    ]
    mock_get_workflow_by_workflow_id.return_value = WorkflowTable(name="update_task_wf")

    with WorkflowInstanceForTests(update_task_wf, "update_task_wf"):
        response = test_client.put("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == snapshot(
        {
            "message": "Added to Update Queue",
            "status": "UPDATED",
        }
    )
    mock_add.assert_called_once()


def test_update_scheduled_task_schedule_not_found(test_client):
    body = {
        "schedule_id": str(uuid4()),
        "name": "Updated Name",
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 10},
    }

    response = test_client.put("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == snapshot({"detail": "Schedule does not exist", "status": 404, "title": "Not Found"})


@patch("orchestrator.api.api_v1.endpoints.schedules.get_linker_entries_by_schedule_ids")
def test_update_scheduled_task_task_not_found(mock_get_linker_entries_by_schedule_ids, test_client):
    body = {
        "schedule_id": str(uuid4()),
        "name": "Updated Name",
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 10},
    }

    mock_get_linker_entries_by_schedule_ids.return_value = [
        WorkflowApschedulerJob(schedule_id=body["schedule_id"], workflow_id=str(uuid4()))
    ]
    response = test_client.put("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == snapshot({"detail": "Task does not exist", "status": 404, "title": "Not Found"})


@patch("orchestrator.api.api_v1.endpoints.schedules.get_workflow_by_workflow_id")
@patch("orchestrator.api.api_v1.endpoints.schedules.get_linker_entries_by_schedule_ids")
def test_update_scheduled_task_unauthorized(
    mock_get_linker_entries_by_schedule_ids, mock_get_workflow_by_workflow_id, test_client
):
    @workflow(target=Target.SYSTEM, authorize_callback=_disallow)
    def unauthorized_update_wf():
        return init >> done

    body = {
        "schedule_id": str(uuid4()),
        "name": "Updated Name",
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 10},
    }

    mock_get_linker_entries_by_schedule_ids.return_value = [
        WorkflowApschedulerJob(schedule_id=body["schedule_id"], workflow_id=str(uuid4()))
    ]
    mock_get_workflow_by_workflow_id.return_value = WorkflowTable(name="unauthorized_update_wf")

    with WorkflowInstanceForTests(unauthorized_update_wf, "unauthorized_update_wf"):
        response = test_client.put("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == snapshot(
        {
            "detail": "User is not authorized to manage schedule with 'unauthorized_update_wf' task",
            "status": 403,
            "title": "Forbidden",
        }
    )


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
    assert response.json() == snapshot(
        {
            "message": "Added to Delete Queue",
            "status": "DELETED",
        }
    )
    mock_add.assert_called_once()

from http import HTTPStatus
from unittest.mock import patch
from uuid import uuid4

from inline_snapshot import snapshot

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.db.models import WorkflowApschedulerJob, WorkflowTable
from orchestrator.targets import Target
from orchestrator.workflow import done, init, workflow
from test.unit_tests.workflows import WorkflowInstanceForTests


@patch("orchestrator.api.api_v1.endpoints.schedules.add_scheduled_task_to_queue")
def test_create_scheduled_task(mock_add, test_client):
    workflow_name = "test_task"

    body = {
        "name": "Test Job",
        "workflow_name": workflow_name,
        "workflow_id": str(uuid4()),
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 30},
    }

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    @workflow(workflow_name, target=Target.SYSTEM, authorize_callback=allow)
    def test_task():
        return init >> done

    with WorkflowInstanceForTests(test_task, workflow_name):
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
    workflow_name = "test_task"

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    @workflow(workflow_name, target=Target.SYSTEM, authorize_callback=allow)
    def test_task():
        return init >> done

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


def test_create_scheduled_task_unauthorized_to_schedule_task(test_client):
    workflow_name = "unauthorized_task"

    body = {
        "name": "Test Job",
        "workflow_name": workflow_name,
        "workflow_id": str(uuid4()),
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 30},
    }

    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    @workflow(workflow_name, target=Target.SYSTEM, authorize_callback=disallow)
    def unauthorized_task():
        return init >> done

    with WorkflowInstanceForTests(unauthorized_task, workflow_name):
        response = test_client.post("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == snapshot(
        {
            "detail": "User is not authorized to manage schedule with 'unauthorized_task' task",
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
    workflow_name = "test_task"

    body = {
        "schedule_id": str(uuid4()),
        "name": "Updated Name",
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 10},
    }

    mock_get_linker_entries_by_schedule_ids.return_value = [
        WorkflowApschedulerJob(schedule_id=body["schedule_id"], workflow_id=str(uuid4()))
    ]
    mock_get_workflow_by_workflow_id.return_value = WorkflowTable(name=workflow_name)

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    @workflow(workflow_name, target=Target.SYSTEM, authorize_callback=allow)
    def test_task():
        return init >> done

    with WorkflowInstanceForTests(test_task, workflow_name):
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
def test_update_scheduled_task_unauthorized_to_schedule_task(
    mock_get_linker_entries_by_schedule_ids, mock_get_workflow_by_workflow_id, test_client
):
    workflow_name = "unauthorized_task"

    body = {
        "schedule_id": str(uuid4()),
        "name": "Updated Name",
        "trigger": "interval",
        "trigger_kwargs": {"seconds": 10},
    }

    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    @workflow(workflow_name, target=Target.SYSTEM, authorize_callback=disallow)
    def unauthorized_task():
        return init >> done

    mock_get_linker_entries_by_schedule_ids.return_value = [
        WorkflowApschedulerJob(schedule_id=body["schedule_id"], workflow_id=str(uuid4()))
    ]
    mock_get_workflow_by_workflow_id.return_value = WorkflowTable(name=workflow_name)

    with WorkflowInstanceForTests(unauthorized_task, workflow_name):
        response = test_client.put("/api/schedules/", json=body)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == snapshot(
        {
            "detail": "User is not authorized to manage schedule with 'unauthorized_task' task",
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

import time
import uuid
from http import HTTPStatus
from threading import Condition, Event
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.config.assignee import Assignee
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    SubscriptionTable,
    db,
)
from orchestrator.security import authenticate
from orchestrator.services.processes import shutdown_thread_pool
from orchestrator.services.settings import get_engine_settings
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus, done, init, step, workflow
from test.unit_tests.helpers import URL_STR_TYPE
from test.unit_tests.workflows import WorkflowInstanceForTests

test_condition = Condition()


@pytest.fixture
def long_running_workflow():
    @step("Long Running Step")
    def long_running_step():
        with test_condition:
            test_condition.wait()
        return {"done": True}

    @workflow("Long Running Workflow")
    def long_running_workflow_py():
        return init >> long_running_step >> long_running_step >> done

    with WorkflowInstanceForTests(long_running_workflow_py, "long_running_workflow_py"):
        yield "long_running_workflow_py"


@pytest.fixture
def started_process(test_workflow, generic_subscription_1):
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id, workflow_id=test_workflow.workflow_id, last_status=ProcessStatus.SUSPENDED
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status="success", state={})
    insert_step = ProcessStepTable(
        process_id=process_id,
        name="Insert UUID in state",
        status="success",
        state={"subscription_id": generic_subscription_1},
    )
    check_step = ProcessStepTable(
        process_id=process_id,
        name="Test that it is a string now",
        status="success",
        state={"subscription_id": generic_subscription_1},
    )
    step = ProcessStepTable(
        process_id=process_id, name="Modify", status="suspend", state={"subscription_id": generic_subscription_1}
    )

    process_subscription = ProcessSubscriptionTable(process_id=process_id, subscription_id=generic_subscription_1)

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(insert_step)
    db.session.add(check_step)
    db.session.add(step)
    db.session.add(process_subscription)
    db.session.commit()

    return process_id


def test_show(test_client, started_process):
    response = test_client.get(f"/api/processes/{started_process}")
    assert HTTPStatus.OK == response.status_code
    process = response.json()
    assert "workflow_for_testing_processes_py", process["workflow_name"]


def test_show_invalid_uuid(test_client):
    response = test_client.get("/api/processes/wrong")
    assert response.status_code == 422


def test_show_not_found(test_client, started_process):
    response = test_client.get("/api/processes/120d31e4-9166-47cb-ad37-b78072c7ab8b")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_delete_process(responses, test_client, started_process):
    processes = test_client.get("/api/processes").json()
    before_delete_count = len(processes)

    response = test_client.delete(f"/api/processes/{started_process}")
    assert HTTPStatus.NO_CONTENT == response.status_code
    assert before_delete_count - 1 == len(test_client.get("/api/processes").json())


def test_delete_process_404(test_client, started_process):
    response = test_client.delete(f"/api/processes/{uuid4()}")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_long_running_pause(test_client, long_running_workflow):
    app_settings.TESTING = False
    # Start the workflow
    response = test_client.post(f"/api/processes/{long_running_workflow}", json=[{}])
    assert (
        HTTPStatus.CREATED == response.status_code
    ), f"Invalid response status code (response data: {response.json()})"

    process_id = response.json()["id"]

    response = test_client.get(f"api/processes/{process_id}")
    assert HTTPStatus.OK == response.status_code

    # Let it run until the first lock step is started
    time.sleep(1)

    response = test_client.put("/api/settings/status", json={"global_lock": True})
    assert response.json()["global_lock"] is True
    assert response.json()["running_processes"] == 1
    assert response.json()["global_status"] == "PAUSING"

    # Let it run until completing the first lock step
    with test_condition:
        test_condition.notify_all()
    time.sleep(1)

    # Make sure the running_processes is decreased and status is updated.
    response = test_client.get("/api/settings/status")
    assert response.json()["global_lock"] is True
    assert response.json()["running_processes"] == 0
    assert response.json()["global_status"] == "PAUSED"

    response = test_client.get(f"api/processes/{process_id}")
    assert len(response.json()["steps"]) == 4
    assert response.json()["current_state"]["done"] is True
    # assume ordered steplist
    assert response.json()["steps"][3]["status"] == "pending"

    response = test_client.put("/api/settings/status", json={"global_lock": False})

    # Make sure it started again
    time.sleep(1)

    assert response.json()["global_lock"] is False
    assert response.json()["running_processes"] == 1
    assert response.json()["global_status"] == "RUNNING"

    # Let it finish after second lock step
    with test_condition:
        test_condition.notify_all()
    time.sleep(1)

    response = test_client.get(f"api/processes/{process_id}")
    assert HTTPStatus.OK == response.status_code
    # assume ordered steplist
    assert response.json()["steps"][3]["status"] == "complete"

    app_settings.TESTING = True


def test_service_unavailable_engine_locked(test_client, test_workflow):
    engine_settings = get_engine_settings()
    engine_settings.global_lock = True
    db.session.flush()

    response = test_client.post(f"/api/processes/{test_workflow}", json=[{}])

    assert HTTPStatus.SERVICE_UNAVAILABLE == response.status_code


def test_complete_workflow(test_client, test_workflow):
    response = test_client.post(f"/api/processes/{test_workflow.name}", json=[{}])

    assert (
        HTTPStatus.CREATED == response.status_code
    ), f"Invalid response status code (response data: {response.json()})"

    process_id = response.json()["id"]

    response = test_client.get(f"api/processes/{process_id}")
    assert HTTPStatus.OK == response.status_code

    process = response.json()
    assert Assignee.CHANGES == process["assignee"]
    assert "suspended" == process["last_status"]

    steps = process["steps"]
    assert "success" == steps[0]["status"]

    response = test_client.get(f"/api/processes/{process_id}")
    assert response.json()["form"] == {
        "title": "unknown",
        "type": "object",
        "properties": {"generic_select": {"$ref": "#/$defs/TestChoice"}},
        "additionalProperties": False,
        "required": ["generic_select"],
        "$defs": {"TestChoice": {"enum": ["A", "B", "C"], "title": "TestChoice", "type": "string"}},
    }

    # Check type validation
    user_input = {"generic_select": 123}
    response = test_client.put(f"/api/processes/{process_id}/resume", json=[user_input])
    assert HTTPStatus.BAD_REQUEST == response.status_code
    assert response.json()["validation_errors"] == [
        {
            "ctx": {"expected": "'A', 'B' or 'C'"},
            "input": 123,
            "loc": ["generic_select"],
            "msg": "Input should be 'A', 'B' or 'C'",
            "type": "enum",
        }
        | URL_STR_TYPE
    ]

    # Check choice validation
    user_input = {"generic_select": "123"}
    response = test_client.put(f"/api/processes/{process_id}/resume", json=[user_input])
    assert HTTPStatus.BAD_REQUEST == response.status_code
    assert response.json()["validation_errors"] == [
        {
            "ctx": {"expected": "'A', 'B' or 'C'"},
            "input": "123",
            "loc": ["generic_select"],
            "msg": "Input should be 'A', 'B' or 'C'",
            "type": "enum",
        }
        | URL_STR_TYPE
    ]

    response = test_client.get(f"api/processes/{process_id}")

    process = response.json()
    assert "suspended" == process["last_status"]

    # Now for real
    user_input = {"generic_select": "A"}

    response = test_client.put(f"/api/processes/{process_id}/resume", json=[user_input])
    assert HTTPStatus.NO_CONTENT == response.status_code

    process = test_client.get(f"api/processes/{process_id}").json()
    assert "completed" == process["last_status"]


def test_abort_process(test_client, started_process):
    response = test_client.put(f"/api/processes/{started_process}/abort")
    assert HTTPStatus.NO_CONTENT == response.status_code

    aborted_process = test_client.get(f"/api/processes/{started_process}").json()
    assert "aborted" == aborted_process["last_status"]


def test_new_process_invalid_body(test_client, long_running_workflow):
    response = test_client.post(f"/api/processes/{long_running_workflow}", json=[{"wrong": "body"}])
    assert HTTPStatus.BAD_REQUEST == response.status_code


def test_new_process_invalid_Content_Type(test_client):
    response = test_client.post("/api/processes/terminate_sn8_light_path")
    assert HTTPStatus.UNPROCESSABLE_ENTITY == response.status_code


def test_new_process_post_inconsistent_data(test_client):
    response = test_client.post("/api/processes/terminate_sn8_light_path", json={})
    assert HTTPStatus.UNPROCESSABLE_ENTITY == response.status_code


def test_404_resume(test_client):
    response = test_client.put(f"/api/processes/{uuid.uuid4()}/resume", json={})
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_resume_validations(test_client, started_process):
    process_info_before = test_client.get(f"/api/processes/{started_process}").json()

    response = test_client.put(f"/api/processes/{started_process}/resume", json=[{"generic_select": 123}])
    assert HTTPStatus.BAD_REQUEST == response.status_code
    assert [
        {
            "ctx": {"expected": "'A', 'B' or 'C'"},
            "input": 123,
            "loc": ["generic_select"],
            "msg": "Input should be 'A', 'B' or 'C'",
            "type": "enum",
        }
        | URL_STR_TYPE
    ] == response.json()["validation_errors"]
    process_info_after = test_client.get(f"/api/processes/{started_process}").json()
    excuted_steps_before = [step for step in process_info_before["steps"] if step.get("executed")]
    excuted_steps_after = [step for step in process_info_after["steps"] if step.get("executed")]
    assert len(excuted_steps_after) == len(excuted_steps_before)
    assert process_info_after["last_status"] == "suspended"


def test_resume_with_empty_form(test_client, started_process):
    # Set a default value for the only input so we can submit an empty form
    step = db.session.scalars(
        select(ProcessStepTable).filter(
            ProcessStepTable.name == "Modify", ProcessStepTable.process_id == started_process
        )
    ).one()
    step.state["generic_select"] = "A"
    db.session.add(step)
    db.session.flush()

    process_info_before = test_client.get(f"/api/processes/{started_process}").json()
    response = test_client.put(f"/api/processes/{started_process}/resume", json=[{"generic_select": "A"}])

    assert HTTPStatus.NO_CONTENT == response.status_code
    process_info_after = test_client.get(f"/api/processes/{started_process}").json()
    excuted_steps_before = [step for step in process_info_before["steps"] if step.get("executed")]
    excuted_steps_after = [step for step in process_info_after["steps"] if step.get("executed")]
    assert len(excuted_steps_after) > len(excuted_steps_before)
    assert process_info_after["last_status"] == "completed"


def test_resume_happy_flow(test_client, started_process):
    process_info_before = test_client.get(f"/api/processes/{started_process}").json()
    response = test_client.put(f"/api/processes/{started_process}/resume", json=[{"generic_select": "A"}])

    assert HTTPStatus.NO_CONTENT == response.status_code
    process_info_after = test_client.get(f"/api/processes/{started_process}").json()
    excuted_steps_before = [step for step in process_info_before["steps"] if step.get("executed")]
    excuted_steps_after = [step for step in process_info_after["steps"] if step.get("executed")]
    assert len(excuted_steps_after) > len(excuted_steps_before)
    assert process_info_after["last_status"] == "completed"


def test_resume_with_incorrect_workflow_status(test_client, started_process):
    process = db.session.get(ProcessTable, started_process)
    # setup DB so it looks like this workflow is already resumed
    process.last_status = ProcessStatus.RUNNING
    process.failed_reason = ""
    db.session.commit()

    process_info_before = test_client.get(f"/api/processes/{started_process}").json()
    response = test_client.put(f"/api/processes/{started_process}/resume", json=[{"generic_select": "A"}])
    assert 409 == response.status_code
    process_info_after = test_client.get(f"/api/processes/{started_process}").json()
    excuted_steps_before = [step for step in process_info_before["steps"] if step.get("executed")]
    excuted_steps_after = [step for step in process_info_after["steps"] if step.get("executed")]
    assert len(excuted_steps_after) == len(excuted_steps_before)
    assert process_info_after["last_status"] == "running"


def test_try_resume_completed_workflow(test_client, started_process):
    process = db.session.get(ProcessTable, started_process)
    assert process
    # setup DB so it looks like this workflow is already completed
    process.last_status = ProcessStatus.COMPLETED
    process.failed_reason = ""
    db.session.commit()

    response = test_client.put(f"/api/processes/{started_process}/resume", json=[{}])
    assert 409 == response.status_code


def test_try_resume_resumed_workflow(test_client, started_process):
    process = db.session.get(ProcessTable, started_process)
    assert process
    # setup DB so it looks like this workflow has already been resumed
    process.last_status = ProcessStatus.RESUMED
    process.failed_reason = ""
    db.session.add(process)
    db.session.commit()

    response = test_client.put(f"/api/processes/{started_process}/resume", json=[{}])
    assert 409 == response.status_code


def test_processes_filterable(test_client, mocked_processes, generic_subscription_2, generic_subscription_1):
    response = test_client.get("/api/processes/")
    assert HTTPStatus.OK == response.status_code
    processes = response.json()

    assert len(processes) == 9
    assert "workflow_for_testing_processes_py", processes[0]["workflow"]

    response = test_client.get("/api/processes?filter=lastStatus,completed")
    assert len(response.json()) == 3
    response = test_client.get("/api/processes?filter=lastStatus,suspended")
    assert len(response.json()) == 2
    response = test_client.get("/api/processes?filter=lastStatus,resumed")
    assert len(response.json()) == 2

    product_name = db.session.get(SubscriptionTable, generic_subscription_1).product.name
    response = test_client.get(f"/api/processes?filter=product,{product_name}")
    assert len(response.json()) == 4
    response = test_client.get("/api/processes?sort=assignee,asc")
    assert response.json()[0]["assignee"] == "NOC"
    response = test_client.get("/api/processes?sort=startedAt&filter=isTask,true")
    assert len(response.json()) == 4


def test_processes_filterable_response_model(
    test_client, mocked_processes, generic_subscription_2, generic_subscription_1
):
    response = test_client.get("/api/processes/?sort=startedAt,asc")
    assert HTTPStatus.OK == response.status_code
    processes = response.json()
    assert len(processes) == 9
    process = processes[0]

    assert len(process["subscriptions"]) == 1

    # Check if the other fields are filled with correct data
    del process["process_id"]  # skip process_id as it's dynamic
    del process["product_id"]  # skip product_id as it's dynamic
    del process["workflow_id"]  # skip workflow_id as it's dynamic
    del process["subscriptions"]
    assert process == {
        "customer_id": "2f47f65a-0911-e511-80d0-005056956c1a",
        "workflow_name": "workflow_for_testing_processes_py",
        "is_task": False,
        "assignee": "SYSTEM",
        "last_status": "completed",
        "last_step": "Modify",
        "failed_reason": None,
        "traceback": None,
        "created_by": None,
        "started_at": 1578994200.0,
        "last_modified_at": 1578994800.0,
        "current_state": None,
        "steps": None,
        "form": None,
        "workflow_target": "CREATE",
    }


def test_processes_filterable_response_model_contains_product_info(
    test_client, mocked_processes, generic_subscription_2, generic_subscription_1
):
    response = test_client.get("/api/processes/?sort=startedAt,asc")
    assert HTTPStatus.OK == response.status_code
    processes = response.json()
    assert len(processes) == 9
    process = processes[0]

    assert len(process["subscriptions"]) == 1
    assert process["subscriptions"][0]["product"]["tag"] == "GEN1"
    assert process["subscriptions"][0]["product"]["name"] == "Product 1"


def test_resume_all_processes(test_client, mocked_processes_resumeall):
    """Test resuming all processes."""
    response = test_client.put("/api/processes/resume-all")
    assert HTTPStatus.OK == response.status_code
    assert response.json()["count"] == 3


def test_resume_all_processes_multiple_calls(test_client, mocked_processes_resumeall):
    """Test only 1 of multiple resume-all calls is successful.

    This uses the "MemoryDistlockManager" reference implementation.
    """
    event = Event()

    def resume_noop(*args, **kwargs):
        event.wait(2)  # To keep the lock open for a while

    # Disable Testing setting since we want to run async
    app_settings.TESTING = False

    with mock.patch("orchestrator.services.processes.resume_process", new=resume_noop):
        responses = [test_client.put("/api/processes/resume-all") for _ in range(5)]
        responses.sort(key=lambda r: r.status_code)
        event.set()

    app_settings.TESTING = True

    assert responses[0].status_code == HTTPStatus.OK
    assert responses[0].json()["count"] == 3
    assert all(response.status_code == HTTPStatus.CONFLICT for response in responses[1:])

    # Wait for async tasks to finish to prevent DB session conflicts
    shutdown_thread_pool()


def test_resume_all_processes_nothing_to_do(test_client):
    """Test resuming all process when there are no process to be resumed."""
    response = test_client.put("/api/processes/resume-all")
    assert HTTPStatus.OK == response.status_code
    assert response.json()["count"] == 0


def test_resume_all_processes_value_error(test_client, mocked_processes_resumeall, caplog):
    """Test resuming all processes where one raises ValueError."""
    with mock.patch("orchestrator.services.processes.resume_process") as mocked_resume:
        mocked_resume.side_effect = [None, ValueError("This workflow cannot be resumed"), None]
        response = test_client.put("/api/processes/resume-all")
    assert HTTPStatus.OK == response.status_code
    assert response.json()["count"] == 3  # returns 3 because it's async
    assert "Failed to resume process" in caplog.text  # log should confirm 1 process was not resumed
    assert "Completed resuming processes" in caplog.text


@pytest.mark.parametrize(
    "oidc_user, reporter, expected_user",
    [
        (OIDCUserModel({"name": "alice"}), None, "alice"),
        (OIDCUserModel({"user_name": "alice"}), None, ""),  # without overriding OIDCUserModel, user_name has no effect
        (OIDCUserModel({"name": "alice"}), "bob", "bob"),  # reporter param has precedence over oidc user
    ],
)
def test_create_process_reporter(test_client, fastapi_app, oidc_user, reporter, expected_user):
    # given
    url_params = {"reporter": reporter} if reporter is not None else {}
    fastapi_depends = {authenticate: lambda: oidc_user}
    with (
        mock.patch("orchestrator.api.api_v1.endpoints.processes.start_process") as mock_start_process,
        mock.patch.dict(fastapi_app.dependency_overrides, fastapi_depends),
    ):
        mock_start_process.return_value = uuid.uuid4()
        # when
        response = test_client.post("/api/processes/fake_workflow", json=[], params=url_params)

    # then
    assert response.status_code == 201, response.text
    mock_start_process.assert_called()
    assert mock_start_process.mock_calls[0].kwargs["user"] == expected_user


def test_new_process_without_version(test_client, generic_subscription_1):

    response = test_client.post(
        "/api/processes/modify_note",
        json=[{"subscription_id": generic_subscription_1}, {"note": "test note"}],
    )
    assert HTTPStatus.CREATED == response.status_code
    new_version = db.session.get(SubscriptionTable, generic_subscription_1).version
    assert new_version == 3


def test_new_process_version_check(test_client, generic_subscription_1):
    version = 2

    response = test_client.post(
        "/api/processes/modify_note",
        json=[{"subscription_id": generic_subscription_1, "version": version}, {"note": "test note"}],
    )
    assert HTTPStatus.CREATED == response.status_code
    new_version = db.session.get(SubscriptionTable, generic_subscription_1).version
    assert new_version == version + 1


def test_new_process_lower_version_invalid(test_client, generic_subscription_1):
    response = test_client.post(
        "/api/processes/modify_note",
        json=[{"subscription_id": generic_subscription_1, "version": 0}, {"note": "test note"}],
    )
    assert HTTPStatus.BAD_REQUEST == response.status_code
    payload = response.json()
    assert (
        payload["validation_errors"][0]["msg"] == "Stale data: given version (0) does not match the current version (2)"
    )


def test_new_process_higher_version_invalid(test_client, generic_subscription_1):
    response = test_client.post(
        "/api/processes/modify_note",
        json=[{"subscription_id": generic_subscription_1, "version": 10}, {"note": "test note"}],
    )
    assert HTTPStatus.BAD_REQUEST == response.status_code
    payload = response.json()
    assert (
        payload["validation_errors"][0]["msg"]
        == "Stale data: given version (10) does not match the current version (2)"
    )


def test_unauthorized_to_run_process(test_client):
    def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    @workflow("unauthorized_workflow", target=Target.CREATE, authorize_callback=disallow)
    def unauthorized_workflow():
        return init >> done

    with WorkflowInstanceForTests(unauthorized_workflow, "unauthorized_workflow"):
        response = test_client.post("/api/processes/unauthorized_workflow", json=[{}])
        assert HTTPStatus.FORBIDDEN == response.status_code

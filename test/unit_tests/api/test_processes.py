import time
import uuid
from http import HTTPStatus
from threading import Condition, Event
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.api_v1.endpoints.processes import get_auth_callbacks
from orchestrator.config.assignee import Assignee
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    SubscriptionTable,
    db,
)
from orchestrator.security import authenticate
from orchestrator.services.processes import RESUME_WORKFLOW_REMOVED_ERROR_MSG, can_be_resumed, shutdown_thread_pool
from orchestrator.services.settings import get_engine_settings
from orchestrator.services.tasks import RESUME_WORKFLOW
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.workflow import (
    CALLBACK_TOKEN_KEY,
    ProcessStatus,
    StepList,
    StepStatus,
    done,
    init,
    inputstep,
    make_workflow,
    retrystep,
    step,
    step_group,
    workflow,
)
from orchestrator.workflows.tasks.cleanup_tasks_log import task_clean_up_tasks
from pydantic_forms.core import FormPage
from test.unit_tests.helpers import URL_STR_TYPE
from test.unit_tests.workflows import WorkflowInstanceForTests

test_condition = Condition()
callback_key = "lgjyjNvu-C6vMbaUmjPZPxoJ1t8yS_41ottoe64qP5A"


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
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    insert_step = ProcessStepTable(
        process_id=process_id,
        name="Insert UUID in state",
        status=StepStatus.SUCCESS,
        state={"subscription_id": generic_subscription_1},
    )
    check_step = ProcessStepTable(
        process_id=process_id,
        name="Test that it is a string now",
        status=StepStatus.SUCCESS,
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


def test_delete_process_workflow(responses, test_client, started_process):
    processes = test_client.get("/api/processes").json()
    before_delete_count = len(processes)

    response = test_client.delete(f"/api/processes/{started_process}")
    assert HTTPStatus.BAD_REQUEST == response.status_code
    assert before_delete_count == len(test_client.get("/api/processes").json())


def test_delete_process_task(responses, test_client, started_process):
    process = db.session.get(ProcessTable, started_process)
    process.is_task = True
    db.session.commit()

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
    # Worker-based counting: worker may still be executing, so could be 0 or 1
    assert response.json()["running_processes"] in [0, 1]
    assert response.json()["global_status"] in ["PAUSING", "PAUSED"]

    # Let it run until completing the first lock step
    with test_condition:
        test_condition.notify_all()
    time.sleep(1)

    # Check status after pausing.
    # Worker-based counting: worker has stopped executing, so count is 0
    response = test_client.get("/api/settings/status")
    assert response.json()["global_lock"] is True
    assert response.json()["running_processes"] == 0  # No workers executing
    assert response.json()["global_status"] == "PAUSED"  # Engine is paused (no workers running)

    response = test_client.get(f"api/processes/{process_id}")
    assert len(response.json()["steps"]) == 4
    assert response.json()["current_state"]["done"] is True
    # assume ordered steplist
    assert response.json()["steps"][3]["status"] == "pending"

    # Unlock the engine to resume execution
    response = test_client.put("/api/settings/status", json={"global_lock": False})
    assert response.json()["global_lock"] is False
    # Worker-based counting: monitor updates periodically, so may not reflect worker immediately
    assert response.json()["running_processes"] in [0, 1]
    assert response.json()["global_status"] == "RUNNING"

    # Let it continue executing
    time.sleep(1)

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
    assert StepStatus.SUCCESS == steps[0]["status"]

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


@pytest.mark.parametrize(
    "process_status",
    [status for status in ProcessStatus if not can_be_resumed(status)],
)
def test_try_resume_workflow_with_incorrect_status(test_client, started_process, process_status):
    process = db.session.get(ProcessTable, started_process)
    assert process
    # setup DB so it looks like this workflow has already been resumed
    process.last_status = process_status
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
        "workflow_target": "SYSTEM",
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
        mocked_resume.side_effect = [
            None,
            ValueError(RESUME_WORKFLOW_REMOVED_ERROR_MSG),
            None,
        ]
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
    async def allow(_: object) -> bool:
        return True

    fake_workflow = make_workflow(
        f=lambda _: None,
        description="fake",
        initial_input_form=None,
        target=Target.CREATE,
        steps=StepList([]),
        authorize_callback=allow,
        retry_auth_callback=allow,
    )
    url_params = {"reporter": reporter} if reporter is not None else {}
    fastapi_depends = {authenticate: lambda: oidc_user}
    with (
        mock.patch("orchestrator.api.api_v1.endpoints.processes.get_workflow") as mock_get_workflow,
        mock.patch("orchestrator.api.api_v1.endpoints.processes.start_process") as mock_start_process,
        mock.patch.dict(fastapi_app.dependency_overrides, fastapi_depends),
    ):
        mock_get_workflow.return_value = fake_workflow
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
    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    @workflow("unauthorized_workflow", target=Target.CREATE, authorize_callback=disallow)
    def unauthorized_workflow():
        return init >> done

    with WorkflowInstanceForTests(unauthorized_workflow, "unauthorized_workflow"):
        response = test_client.post("/api/processes/unauthorized_workflow", json=[{}])
        assert HTTPStatus.FORBIDDEN == response.status_code


@pytest.fixture
def authorize_resume_workflow():
    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    class ConfirmForm(FormPage):
        confirm: bool

    @inputstep("authorized_resume", assignee=Assignee.SYSTEM, resume_auth_callback=allow, retry_auth_callback=disallow)
    def authorized_resume(state):
        user_input = yield ConfirmForm
        return user_input.model_dump()

    @inputstep("unauthorized_resume", assignee=Assignee.SYSTEM, resume_auth_callback=disallow)
    def unauthorized_resume(state):
        user_input = yield ConfirmForm
        return user_input.model_dump()

    @workflow("test_auth_workflow", target=Target.CREATE, authorize_callback=allow, retry_auth_callback=disallow)
    def test_auth_workflow():
        return init >> authorized_resume >> unauthorized_resume >> done

    with WorkflowInstanceForTests(test_auth_workflow, "test_auth_workflow") as wf:
        yield wf


@pytest.fixture
def process_on_resumable_inputstep(authorize_resume_workflow):
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_resume_workflow.workflow_id,
        last_status=ProcessStatus.SUSPENDED,
        last_step="Start",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.commit()

    return process_id


@pytest.fixture
def process_on_retriable_inputstep(authorize_resume_workflow):
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_resume_workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="authorized_resume",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    failed_step = ProcessStepTable(process_id=process_id, name="authorized_resume", status=StepStatus.FAILED, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(failed_step)
    db.session.commit()

    return process_id


@pytest.fixture
def process_on_unauthorized_resume(process_on_resumable_inputstep):
    authorize_resume_step = ProcessStepTable(
        process_id=process_on_resumable_inputstep,
        name="authorized_resume",
        status=StepStatus.SUCCESS,
        state={"confirm": True},
    )

    db.session.add(authorize_resume_step)
    db.session.commit()

    return process_on_resumable_inputstep


def test_authorized_resume_input_step(test_client, process_on_resumable_inputstep):
    response = test_client.put(f"/api/processes/{process_on_resumable_inputstep}/resume", json=[{"confirm": True}])
    assert HTTPStatus.NO_CONTENT == response.status_code


def test_unauthorized_resume_input_step_retry(test_client, process_on_retriable_inputstep):
    # The current inputstep should be allowing resumes but not retries, and should be FAILED.
    response = test_client.put(f"/api/processes/{process_on_retriable_inputstep}/resume", json=[{"confirm": True}])
    assert HTTPStatus.FORBIDDEN == response.status_code


def test_unauthorized_resume_input_step(test_client, process_on_unauthorized_resume):
    response = test_client.put(f"/api/processes/{process_on_unauthorized_resume}/resume", json=[{"confirm": True}])
    assert HTTPStatus.FORBIDDEN == response.status_code


async def _A(_: OIDCUserModel) -> bool:
    return True


async def _B(_: OIDCUserModel) -> bool:
    return True


async def _C(_: OIDCUserModel) -> bool:
    return True


async def _D(_: OIDCUserModel) -> bool:
    return True


@pytest.mark.parametrize(
    "policies, decisions",
    [
        ((None, None, None, None), (None, None)),
        ((_A, None, None, None), (_A, _A)),
        ((None, _B, None, None), (None, _B)),
        ((_A, _B, None, None), (_A, _B)),
        ((None, None, _C, None), (_C, _C)),
        ((_A, None, _C, None), (_C, _C)),
        ((None, _B, _C, None), (_C, _C)),
        ((_A, _B, _C, None), (_C, _C)),
        ((None, None, None, _D), (None, _D)),
        ((_A, None, None, _D), (_A, _D)),
        ((None, _B, None, _D), (None, _D)),
        ((_A, _B, None, _D), (_A, _D)),
        ((None, None, _C, _D), (_C, _D)),  # 4
        ((_A, None, _C, _D), (_C, _D)),
        ((None, _B, _C, _D), (_C, _D)),
        ((_A, _B, _C, _D), (_C, _D)),
    ],
)
def test_get_auth_callbacks(policies, decisions):
    @step("bar")
    def bar():
        return {}

    @step("baz")
    def baz():
        return {}

    workflow = make_workflow(
        f=lambda: {},
        description="description",
        initial_input_form=None,
        target=Target.SYSTEM,
        steps=StepList([]),
        authorize_callback=None,
        retry_auth_callback=None,
    )

    auth, retry, step_resume_auth, step_retry_auth = policies
    want_auth, want_retry = decisions
    workflow.authorize_callback = auth
    workflow.retry_auth_callback = retry

    @inputstep("foo", Target.SYSTEM, step_resume_auth, step_retry_auth)
    def foo():
        return {}

    steps = StepList([bar, foo, baz])

    got_auth, got_retry = get_auth_callbacks(steps, workflow)
    assert got_auth == want_auth
    assert got_retry == want_retry


@pytest.fixture
def process_on_await_callback(authorize_resume_workflow):
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_resume_workflow.workflow_id,
        last_status=ProcessStatus.AWAITING_CALLBACK,
        last_step="Action step",
    )
    init_step = ProcessStepTable(
        process_id=process_id, name="Action step", status=StepStatus.SUCCESS, state={CALLBACK_TOKEN_KEY: callback_key}
    )

    db.session.add(process)
    db.session.add(init_step)
    db.session.commit()

    return process_id


@mock.patch("orchestrator.services.tasks.get_celery_task")
@mock.patch("orchestrator.db")
@mock.patch.object(app_settings, "EXECUTOR", "celery")
def test_continue_awaiting_process_endpoint(mock_db, mock_get_celery_task, test_client, process_on_await_callback):
    trigger_task = mock.MagicMock()
    trigger_task.delay.get.return_value = uuid4()
    mock_get_celery_task.return_value = trigger_task

    fake_result = mock.MagicMock()
    fake_result.last_status = "AWAIT_CALLBACK"
    mock_db.session.execute.return_value.scalar_one_or_none.return_value = fake_result

    response = test_client.post(
        f"/api/processes/{process_on_await_callback}/callback/{callback_key}", json={"callback_response": True}
    )
    assert response.status_code == HTTPStatus.OK
    mock_get_celery_task.assert_called_once_with(RESUME_WORKFLOW)


def test_continue_awaiting_process_endpoint_wrong_process_status(test_client, process_on_resumable_inputstep):
    response = test_client.post(
        f"/api/processes/{process_on_resumable_inputstep}/callback/{callback_key}", json={"callback_response": True}
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {
        "detail": "This process is not in an awaiting state.",
        "status": 409,
        "title": "Conflict",
    }


@pytest.fixture
def authorize_step_group_retry_workflow():
    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    steps = StepList([])
    authorized_retry = step_group("authorized_retry", steps, retry_auth_callback=allow)
    unauthorized_retry = step_group("unauthorized_retry", steps, retry_auth_callback=disallow)

    # Default retry is disallow so we can test that authorized_retry overrides this.
    @workflow("test_step_group_workflow", target=Target.CREATE, retry_auth_callback=disallow)
    def test_step_group_workflow():
        return init >> authorized_retry >> unauthorized_retry >> done

    with WorkflowInstanceForTests(test_step_group_workflow, "test_step_group_workflow") as wf:
        yield wf


@pytest.fixture
def process_on_retriable_step_group(authorize_step_group_retry_workflow):
    """A process stuck on a failed step group that CAN be retried."""
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_step_group_retry_workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="authorized_retry",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    failed_step = ProcessStepTable(process_id=process_id, name="authorized_retry", status=StepStatus.FAILED, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(failed_step)
    db.session.commit()

    return process_id


@pytest.fixture
def process_on_unretriable_step_group(authorize_step_group_retry_workflow):
    """A process stuck on a failed step group that CANNOT be retried."""
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_step_group_retry_workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="unauthorized_retry",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    success_step = ProcessStepTable(process_id=process_id, name="authorized_retry", status=StepStatus.SUCCESS, state={})
    failed_step = ProcessStepTable(process_id=process_id, name="unauthorized_retry", status=StepStatus.FAILED, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(success_step)
    db.session.add(failed_step)
    db.session.commit()

    return process_id


def test_authorized_step_group_retry(test_client, process_on_retriable_step_group):
    response = test_client.put(f"/api/processes/{process_on_retriable_step_group}/resume", json=[{"confirm": True}])
    assert HTTPStatus.NO_CONTENT == response.status_code


def test_unauthorized_step_group_retry(test_client, process_on_unretriable_step_group):
    response = test_client.put(f"/api/processes/{process_on_unretriable_step_group}/resume", json=[{"confirm": True}])
    assert HTTPStatus.FORBIDDEN == response.status_code


@pytest.fixture
def authorize_step_retry_workflow():
    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    @step("authorized_retry", retry_auth_callback=allow)
    def authorized_retry(state):
        return

    @step("unauthorized_retry", retry_auth_callback=disallow)
    def unauthorized_retry(state):
        return

    # Default retry is disallow so we can test that authorized_retry overrides this.
    @workflow("test_step_retry_workflow", target=Target.CREATE, retry_auth_callback=disallow)
    def test_step_group_workflow():
        return init >> authorized_retry >> unauthorized_retry >> done

    with WorkflowInstanceForTests(test_step_group_workflow, "test_step_group_workflow") as wf:
        yield wf


@pytest.fixture
def process_on_retriable_step(authorize_step_retry_workflow):
    """A process stuck on a failed step group that CAN be retried."""
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_step_retry_workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="authorized_retry",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    failed_step = ProcessStepTable(process_id=process_id, name="authorized_retry", status=StepStatus.FAILED, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(failed_step)
    db.session.commit()

    return process_id


@pytest.fixture
def process_on_unretriable_step(authorize_step_retry_workflow):
    """A process stuck on a failed step group that CANNOT be retried."""
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_step_retry_workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="unauthorized_retry",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    success_step = ProcessStepTable(process_id=process_id, name="authorized_retry", status=StepStatus.SUCCESS, state={})
    failed_step = ProcessStepTable(process_id=process_id, name="unauthorized_retry", status=StepStatus.FAILED, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(success_step)
    db.session.add(failed_step)
    db.session.commit()

    return process_id


def test_authorized_step_retry(test_client, process_on_retriable_step):
    response = test_client.put(f"/api/processes/{process_on_retriable_step}/resume", json={})
    assert HTTPStatus.NO_CONTENT == response.status_code


def test_unauthorized_step_retry(test_client, process_on_unretriable_step):
    response = test_client.put(f"/api/processes/{process_on_unretriable_step}/resume", json={})
    assert HTTPStatus.FORBIDDEN == response.status_code


@pytest.fixture
def authorize_retrystep_retry_workflow():
    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    @retrystep("authorized_retry", retry_auth_callback=allow)
    def authorized_retry(state):
        return

    @retrystep("unauthorized_retry", retry_auth_callback=disallow)
    def unauthorized_retry(state):
        return

    # Default retry is disallow so we can test that authorized_retry overrides this.
    @workflow("test_retrystep_retry_workflow", target=Target.CREATE, retry_auth_callback=disallow)
    def test_step_group_workflow():
        return init >> authorized_retry >> unauthorized_retry >> done

    with WorkflowInstanceForTests(test_step_group_workflow, "test_step_group_workflow") as wf:
        yield wf


@pytest.fixture
def process_on_retriable_retrystep(authorize_retrystep_retry_workflow):
    """A process stuck on a failed retrystep that CAN be retried."""
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_retrystep_retry_workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="authorized_retry",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    failed_step = ProcessStepTable(process_id=process_id, name="authorized_retry", status=StepStatus.FAILED, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(failed_step)
    db.session.commit()

    return process_id


@pytest.fixture
def process_on_unretriable_retrystep(authorize_retrystep_retry_workflow):
    """A process stuck on a failed retrystep that CANNOT be retried."""
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=authorize_retrystep_retry_workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="unauthorized_retry",
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    success_step = ProcessStepTable(process_id=process_id, name="authorized_retry", status=StepStatus.SUCCESS, state={})
    failed_step = ProcessStepTable(process_id=process_id, name="unauthorized_retry", status=StepStatus.FAILED, state={})

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(success_step)
    db.session.add(failed_step)
    db.session.commit()

    return process_id


def test_authorized_retrystep_retry(test_client, process_on_retriable_retrystep):
    response = test_client.put(f"/api/processes/{process_on_retriable_retrystep}/resume", json={})
    assert HTTPStatus.NO_CONTENT == response.status_code


def test_unauthorized_retrystep_retry(test_client, process_on_unretriable_retrystep):
    response = test_client.put(f"/api/processes/{process_on_unretriable_retrystep}/resume", json={})
    assert HTTPStatus.FORBIDDEN == response.status_code


@pytest.fixture
def fastapi_app_for_auth_callbacks(fastapi_app):
    """Reset auth callbacks after each fixture use.

    Fixture fastapi_app has scope "session", so its cleanup won't run between tests.
    This wraps the session fixture with a per-test fixture to ensure these callbacks are reset.
    """
    yield fastapi_app
    # Clear internal RBAC settings
    fastapi_app.register_internal_authorize_callback(None)
    fastapi_app.register_internal_retry_auth_callback(None)


def test_internal_authorize_callback(test_client, fastapi_app_for_auth_callbacks):
    """Test RBAC callbacks can restrict access to internal workflows."""

    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    with mock.patch("orchestrator.api.api_v1.endpoints.processes.start_process") as mock_start_process:
        # Just return a bogus UUID instead of actually starting a process.
        mock_start_process.return_value = uuid4()

        # Test that we succeed in the default case (no authorizer)
        response = test_client.post("/api/processes/task_clean_up_tasks", json=[{}])
        assert HTTPStatus.CREATED == response.status_code

        # Test that disallow now blocks us
        fastapi_app_for_auth_callbacks.register_internal_authorize_callback(disallow)
        response = test_client.post("/api/processes/task_clean_up_tasks", json=[{}])
        assert HTTPStatus.FORBIDDEN == response.status_code


@pytest.fixture
def internal_process_on_retry_step():
    """A task_clean_up_tasks process stuck on a failed step."""
    # Don't know the UUID of task_clean_up_tasks at test time, so we temporarily register a copy of it.
    with WorkflowInstanceForTests(task_clean_up_tasks, "task_clean_up_tasks_again") as wf:
        process_id = uuid4()
        process = ProcessTable(
            process_id=process_id,
            workflow_id=wf.workflow_id,
            last_status=ProcessStatus.FAILED,
            last_step="remove_tasks",
        )
        init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
        failed_step = ProcessStepTable(process_id=process_id, name="remove_tasks", status=StepStatus.FAILED, state={})

        db.session.add(process)
        db.session.add(init_step)
        db.session.add(failed_step)
        db.session.commit()

        # Yield, not return, since we need the workflow to persist for the duration of the test.
        yield process_id


def test_internal_retry_auth_callback(test_client, fastapi_app_for_auth_callbacks, internal_process_on_retry_step):
    """Test that RBAC callbacks can manage access to retrying internal workflows."""

    async def disallow(_: OIDCUserModel | None = None) -> bool:
        return False

    async def allow(_: OIDCUserModel | None = None) -> bool:
        return True

    with mock.patch("orchestrator.api.api_v1.endpoints.processes.start_process") as mock_start_process:
        # Just return a bogus UUID instead of actually starting a process.
        mock_start_process.return_value = uuid4()

        # Start with disallow. This should block us.
        fastapi_app_for_auth_callbacks.register_internal_retry_auth_callback(disallow)
        response = test_client.put(f"/api/processes/{internal_process_on_retry_step}/resume", json={})
        assert HTTPStatus.FORBIDDEN == response.status_code

        # Update to allow. This should succeed.
        fastapi_app_for_auth_callbacks.register_internal_retry_auth_callback(allow)
        response = test_client.put(f"/api/processes/{internal_process_on_retry_step}/resume", json={})
        assert HTTPStatus.NO_CONTENT == response.status_code

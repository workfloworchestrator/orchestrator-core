import time
from http import HTTPStatus
from threading import Condition
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.websockets import WebSocketDisconnect

from orchestrator.config.assignee import Assignee
from orchestrator.db import ProcessStepTable, ProcessSubscriptionTable, ProcessTable, WorkflowTable, db
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.utils.json import json_loads
from orchestrator.websocket import websocket_manager
from orchestrator.workflow import ProcessStatus, StepStatus, done, init, step, workflow
from test.unit_tests.workflows import WorkflowInstanceForTests

test_condition = Condition()

LONG_RUNNING_STEP = "Long Running Step"
IMMEDIATE_STEP = "Immediate Step"


@pytest.fixture
def long_running_workflow():
    @step(LONG_RUNNING_STEP)
    def long_running_step():
        with test_condition:
            test_condition.wait()
        return {"done": True}

    @step(IMMEDIATE_STEP)
    def immediate_step():
        return {"done": True}

    @workflow("Long Running Workflow")
    def long_running_workflow_py():
        return init >> long_running_step >> immediate_step >> long_running_step >> done

    with WorkflowInstanceForTests(long_running_workflow_py, "long_running_workflow_py"):

        db_workflow = WorkflowTable(name="long_running_workflow_py", target=Target.MODIFY)
        db.session.add(db_workflow)
        db.session.commit()

        yield "long_running_workflow_py"


@pytest.fixture
def completed_process(test_workflow, generic_subscription_1):
    pid = uuid4()
    process = ProcessTable(pid=pid, workflow=test_workflow, last_status=ProcessStatus.COMPLETED)
    init_step = ProcessStepTable(pid=pid, name="Start", status=StepStatus.SUCCESS, state={})
    insert_step = ProcessStepTable(
        pid=pid,
        name="Insert UUID in state",
        status=StepStatus.SUCCESS,
        state={"subscription_id": generic_subscription_1},
    )
    check_step = ProcessStepTable(
        pid=pid,
        name="Test that it is a string now",
        status=StepStatus.SUCCESS,
        state={"subscription_id": generic_subscription_1},
    )
    step = ProcessStepTable(
        pid=pid, name="Modify", status=StepStatus.SUCCESS, state={"subscription_id": generic_subscription_1}
    )

    process_subscription = ProcessSubscriptionTable(pid=pid, subscription_id=generic_subscription_1)

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(insert_step)
    db.session.add(check_step)
    db.session.add(step)
    db.session.add(process_subscription)
    db.session.commit()

    return pid


def test_websocket_process_detail_invalid_uuid(test_client):
    pid = uuid4()

    try:
        with test_client.websocket_connect(f"/api/processes/{pid}?token=") as websocket:
            data = websocket.receive_text()
            error = json_loads(data)["error"]
            assert "Not Found" == error["title"]
            assert f"Process with pid {pid} not found" == error["detail"]
            assert 404 == error["status_code"]

            # close and call receive_text to check websocket close exception
            websocket.close()
            data = websocket.receive_text()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE


def test_websocket_process_detail_completed(test_client, completed_process):
    try:
        with test_client.websocket_connect(f"api/processes/{completed_process}?token=") as websocket:
            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["status"] == "completed"

            # close and call receive_text to check websocket close exception
            websocket.close()
            data = websocket.receive_text()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE


def test_websocket_process_detail_workflow(test_client, long_running_workflow):
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    app_settings.TESTING = False

    # Start the workflow
    response = test_client.post(f"/api/processes/{long_running_workflow}", json=[{}])
    assert (
        HTTPStatus.CREATED == response.status_code
    ), f"Invalid response status code (response data: {response.json()})"

    pid = response.json()["id"]

    response = test_client.get(f"api/processes/{pid}")
    assert HTTPStatus.OK == response.status_code

    # Make sure it started again
    time.sleep(1)

    try:
        with test_client.websocket_connect(f"api/processes/{pid}?token=") as websocket:
            # Check the websocket messages.
            # the initial process details.
            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["workflow_name"] == "long_running_workflow_py"
            assert process["status"] == ProcessStatus.RUNNING

            # Let first long step finish, receive_text would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(1)

            # message step 1.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["status"] == ProcessStatus.RUNNING
            assert step["name"] == LONG_RUNNING_STEP
            assert step["status"] == StepStatus.SUCCESS

            # message step 2.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["status"] == ProcessStatus.RUNNING
            assert step["name"] == IMMEDIATE_STEP
            assert step["status"] == StepStatus.SUCCESS

            # Let second long step finish, receive_text would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(1)

            # message step 3.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["status"] == ProcessStatus.RUNNING
            assert step["name"] == LONG_RUNNING_STEP
            assert step["status"] == StepStatus.SUCCESS

            # message step 4.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["status"] == ProcessStatus.COMPLETED
            assert step["name"] == "Done"
            assert step["status"] == StepStatus.COMPLETE
            assert json_data["close"] is True

            # close and call receive_text to check websocket close exception
            websocket.close()
            data = websocket.receive_text()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE
    except AssertionError as e:
        # Finish steps so the test doesn't get stuck waiting forever.
        with test_condition:
            test_condition.notify_all()
        with test_condition:
            test_condition.notify_all()
        app_settings.TESTING = True
        raise e
    app_settings.TESTING = True


def test_websocket_process_detail_with_suspend(test_client, test_workflow):
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    response = test_client.post(f"/api/processes/{test_workflow}", json=[{}])

    assert (
        HTTPStatus.CREATED == response.status_code
    ), f"Invalid response status code (response data: {response.json()})"

    pid = response.json()["id"]

    try:
        with test_client.websocket_connect(f"api/processes/{pid}?token=") as websocket:
            # Resume process
            user_input = {"generic_select": "A"}

            response = test_client.put(f"/api/processes/{pid}/resume", json=[user_input])
            assert HTTPStatus.NO_CONTENT == response.status_code

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["status"] == ProcessStatus.SUSPENDED
            assert process["assignee"] == Assignee.CHANGES

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["status"] == ProcessStatus.RUNNING
            assert process["assignee"] == Assignee.CHANGES

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["status"] == ProcessStatus.COMPLETED
            assert process["assignee"] == Assignee.SYSTEM

            # close and call receive_text to check websocket close exception
            websocket.close()
            data = websocket.receive_text()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE


def test_websocket_process_detail_with_abort(test_client, test_workflow):
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    response = test_client.post(f"/api/processes/{test_workflow}", json=[{}])

    assert (
        HTTPStatus.CREATED == response.status_code
    ), f"Invalid response status code (response data: {response.json()})"

    pid = response.json()["id"]

    try:
        with test_client.websocket_connect(f"api/processes/{pid}?token=") as websocket:
            # Abort process
            response = test_client.put(f"/api/processes/{pid}/abort")
            assert HTTPStatus.NO_CONTENT == response.status_code

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["status"] == ProcessStatus.SUSPENDED
            assert process["assignee"] == Assignee.CHANGES

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["status"] == ProcessStatus.ABORTED
            assert process["assignee"] == Assignee.SYSTEM

            # close and call receive_text to check websocket close exception
            websocket.close()
            data = websocket.receive_text()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE


def test_websocket_process_list_multiple_workflows(test_client, long_running_workflow, test_workflow):
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    app_settings.TESTING = False

    # Start long_running_workflow
    response = test_client.post(f"/api/processes/{long_running_workflow}", json=[{}])
    assert (
        HTTPStatus.CREATED == response.status_code
    ), f"Invalid response status code (response data: {response.json()})"

    long_running_workflow_pid = response.json()["id"]

    response = test_client.get(f"api/processes/{long_running_workflow_pid}")
    assert HTTPStatus.OK == response.status_code

    try:
        with test_client.websocket_connect("api/processes/all/?token=") as websocket:
            # start test_workflow
            test_workflow_response = test_client.post(f"/api/processes/{test_workflow}", json=[{}])

            assert (
                HTTPStatus.CREATED == test_workflow_response.status_code
            ), f"Invalid response status code (response data: {test_workflow_response.json()})"

            test_workflow_response_pid = test_workflow_response.json()["id"]

            # Make sure it started again
            time.sleep(1)

            # Let first long step finish, receive_text would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(1)

            # Let second long step finish, receive_text would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(1)

            # close and call receive_text to check websocket close exception
            websocket.close()

            # Check the websocket messages.
            # message process workflow_for_testing_processes_py 1.
            data = websocket.receive_text()
            json_data = json_loads(data)
            failed_processes = json_data["failedProcesses"]
            assert len(failed_processes) == 0

            # message process workflow_for_testing_processes_py 1.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "workflow_for_testing_processes_py"
            assert process["id"] == test_workflow_response_pid
            assert process["assignee"] == Assignee.SYSTEM
            assert process["status"] == ProcessStatus.RUNNING
            assert process["step"] == "Start"
            assert step["name"] == "Start"
            assert step["status"] == StepStatus.SUCCESS

            # message process workflow_for_testing_processes_py 2.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "workflow_for_testing_processes_py"
            assert process["id"] == test_workflow_response_pid
            assert process["assignee"] == Assignee.SYSTEM
            assert process["status"] == ProcessStatus.RUNNING
            assert process["step"] == "Insert UUID in state"
            assert step["name"] == "Insert UUID in state"
            assert step["status"] == StepStatus.SUCCESS

            # message process workflow_for_testing_processes_py 3.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "workflow_for_testing_processes_py"
            assert process["id"] == test_workflow_response_pid
            assert process["assignee"] == Assignee.SYSTEM
            assert process["status"] == ProcessStatus.RUNNING
            assert process["step"] == "Test that it is a string now"
            assert step["name"] == "Test that it is a string now"
            assert step["status"] == StepStatus.SUCCESS

            # message process workflow_for_testing_processes_py 4.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "workflow_for_testing_processes_py"
            assert process["id"] == test_workflow_response_pid
            assert process["assignee"] == Assignee.CHANGES
            assert process["status"] == ProcessStatus.SUSPENDED
            assert process["step"] == "Modify"
            assert step["name"] == "Modify"
            assert step["status"] == StepStatus.SUSPEND

            # message process long_running_workflow_py 1.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "long_running_workflow_py"
            assert process["id"] == long_running_workflow_pid
            assert process["assignee"] == Assignee.SYSTEM
            assert process["status"] == ProcessStatus.RUNNING
            assert process["step"] == LONG_RUNNING_STEP
            assert step["name"] == LONG_RUNNING_STEP
            assert step["status"] == StepStatus.SUCCESS

            # message process long_running_workflow_py 2.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "long_running_workflow_py"
            assert process["id"] == long_running_workflow_pid
            assert process["assignee"] == Assignee.SYSTEM
            assert process["status"] == ProcessStatus.RUNNING
            assert process["step"] == IMMEDIATE_STEP
            assert step["name"] == IMMEDIATE_STEP
            assert step["status"] == StepStatus.SUCCESS

            # message process long_running_workflow_py 3.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "long_running_workflow_py"
            assert process["id"] == long_running_workflow_pid
            assert process["assignee"] == Assignee.SYSTEM
            assert process["status"] == ProcessStatus.RUNNING
            assert process["step"] == LONG_RUNNING_STEP
            assert step["name"] == LONG_RUNNING_STEP
            assert step["status"] == StepStatus.SUCCESS

            # message process long_running_workflow_py 4.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            step = json_data["step"]
            assert process["workflow_name"] == "long_running_workflow_py"
            assert process["id"] == long_running_workflow_pid
            assert process["assignee"] == Assignee.SYSTEM
            assert process["status"] == ProcessStatus.COMPLETED
            assert process["step"] == "Done"
            assert step["name"] == "Done"
            assert step["status"] == StepStatus.COMPLETE
            assert json_data["close"] is True
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE
    except AssertionError as e:
        # Finish steps so the test doesn't get stuck waiting forever.
        with test_condition:
            test_condition.notify_all()
        with test_condition:
            test_condition.notify_all()
        app_settings.TESTING = True
        raise e
    app_settings.TESTING = True

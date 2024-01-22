import time
from collections.abc import Generator
from http import HTTPStatus
from threading import Condition
from typing import Any
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.websockets import WebSocketDisconnect

from orchestrator.config.assignee import Assignee
from orchestrator.db import ProcessStepTable, ProcessSubscriptionTable, ProcessTable, db
from orchestrator.settings import app_settings
from orchestrator.types import UUIDstr
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
        yield "long_running_workflow_py"


@pytest.fixture
def test_workflow_2(generic_subscription_1: UUIDstr, generic_product_type_1) -> Generator:
    _, GenericProductOne = generic_product_type_1

    @step("Insert UUID in state")
    def insert_object():
        return {"subscription_id": str(uuid4()), "model": GenericProductOne.from_subscription(generic_subscription_1)}

    @step("Test that it is a string now")
    def check_object(subscription_id: Any, model: dict) -> None:
        # This is actually a test. It would be nicer to have this in a proper test but that takes to much setup that
        # already happens here. So we hijack this fixture and run this test for all tests that use this fixture
        # (which should not be an issue)
        assert isinstance(subscription_id, str)
        assert isinstance(model, dict)

    @step("immediate step")
    def immediate_step():
        return {"done": True}

    @workflow("Workflow")
    def workflow_for_testing_processes_2_py():
        return init >> insert_object >> check_object >> immediate_step >> done

    with WorkflowInstanceForTests(workflow_for_testing_processes_2_py, "workflow_for_testing_processes_2_py") as wf:
        yield wf


@pytest.fixture
def completed_process(test_workflow, generic_subscription_1):
    process_id = uuid4()
    process = ProcessTable(process_id=process_id, workflow_name=test_workflow, last_status=ProcessStatus.COMPLETED)
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
        process_id=process_id,
        name="Modify",
        status=StepStatus.SUCCESS,
        state={"subscription_id": generic_subscription_1},
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


# long running workflow test only works locally and with memory type
def test_websocket_process_detail_workflow(test_client, long_running_workflow):
    if websocket_manager.broadcaster_type != "memory" or app_settings.ENVIRONMENT != "local":
        pytest.skip("test does not work with redis")

    app_settings.TESTING = False

    # Start the workflow
    response = test_client.post(f"/api/processes/{long_running_workflow}", json=[{}])
    assert (
        HTTPStatus.CREATED == response.status_code
    ), f"Invalid response status code (response data: {response.json()})"

    process_id = response.json()["id"]

    response = test_client.get(f"api/processes/{process_id}")
    assert HTTPStatus.OK == response.status_code

    # Make sure it started again
    time.sleep(1)

    try:
        with test_client.websocket_connect("api/processes/all/?token=") as websocket:
            # Check the websocket messages.
            # the initial process details.

            # WITH AN PACKAGE UPDATE IT DOES NOT SEND THIS FIRST MESSAGE ANYMORE
            # data = websocket.receive_text()
            # process = json_loads(data)["process"]
            # assert process["workflow_name"] == "long_running_workflow_py"
            # assert process["last_status"] == ProcessStatus.RUNNING

            # Let first long step finish, receive_text would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(1)

            # message step 1.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            assert process["last_status"] == ProcessStatus.RUNNING
            assert process["workflow_name"] == "long_running_workflow_py"
            assert process["steps"][1]["name"] == LONG_RUNNING_STEP
            assert process["steps"][1]["status"] == StepStatus.SUCCESS

            # message step 2.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            assert process["last_status"] == ProcessStatus.RUNNING
            assert process["steps"][2]["name"] == IMMEDIATE_STEP
            assert process["steps"][2]["status"] == StepStatus.SUCCESS

            # Let second long step finish, receive_text would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(1)

            # message step 3.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            assert process["last_status"] == ProcessStatus.RUNNING
            assert process["steps"][3]["name"] == LONG_RUNNING_STEP
            assert process["steps"][3]["status"] == StepStatus.SUCCESS

            # message step 4.
            data = websocket.receive_text()
            json_data = json_loads(data)
            process = json_data["process"]
            assert process["last_status"] == ProcessStatus.COMPLETED
            assert process["steps"][4]["name"] == "Done"
            assert process["steps"][4]["status"] == StepStatus.COMPLETE

            # close and call receive_text to check websocket close exception
            websocket.close()
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

    with test_condition:
        test_condition.notify_all()
    app_settings.TESTING = True


def test_websocket_process_detail_with_suspend(test_client, test_workflow):
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    response = test_client.post(f"/api/processes/{test_workflow.name}", json=[{}])

    assert (
        response.status_code == HTTPStatus.CREATED
    ), f"Invalid response status code (response data: {response.json()})"

    process_id = response.json()["id"]

    try:
        with test_client.websocket_connect("api/processes/all/?token=") as websocket:
            # Resume process
            user_input = {"generic_select": "A"}

            response = test_client.put(f"/api/processes/{process_id}/resume", json=[user_input])
            assert HTTPStatus.NO_CONTENT == response.status_code

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["last_status"] == ProcessStatus.RUNNING
            assert process["assignee"] == Assignee.CHANGES

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["last_status"] == ProcessStatus.COMPLETED
            assert process["assignee"] == Assignee.SYSTEM

            # close and call receive_text to check websocket close exception
            websocket.close()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE


def test_websocket_process_detail_with_abort(test_client, test_workflow):
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    response = test_client.post(f"/api/processes/{test_workflow.name}", json=[{}])

    assert (
        response.status_code == HTTPStatus.CREATED
    ), f"Invalid response status code (response data: {response.json()})"

    process_id = response.json()["id"]

    try:
        with test_client.websocket_connect("api/processes/all/?token=") as websocket:
            # Abort process
            response = test_client.put(f"/api/processes/{process_id}/abort")
            assert HTTPStatus.NO_CONTENT == response.status_code

            data = websocket.receive_text()
            process = json_loads(data)["process"]
            assert process["last_status"] == ProcessStatus.ABORTED
            assert process["assignee"] == Assignee.SYSTEM

            # close and call receive_text to check websocket close exception
            websocket.close()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE


def test_websocket_process_list_multiple_workflows(test_client, test_workflow, test_workflow_2):
    # This tests the ProcessDataBroadcastThread as well
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    # to keep track of the amount of websocket messages
    message_count = 0

    expected_workflow_1_steps = [
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.RUNNING,
            "last_step": "Start",
            "step_status": StepStatus.SUCCESS,
        },
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.RUNNING,
            "last_step": "Insert UUID in state",
            "step_status": StepStatus.SUCCESS,
        },
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.RUNNING,
            "last_step": "Test that it is a string now",
            "step_status": StepStatus.SUCCESS,
        },
        {
            "assignee": Assignee.CHANGES,
            "status": ProcessStatus.SUSPENDED,
            "last_step": "Modify",
            "step_status": StepStatus.SUSPEND,
        },
    ]

    expected_workflow_2_steps = [
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.RUNNING,
            "last_step": "Start",
            "step_status": StepStatus.SUCCESS,
        },
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.RUNNING,
            "last_step": "Insert UUID in state",
            "step_status": StepStatus.SUCCESS,
        },
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.RUNNING,
            "last_step": "Test that it is a string now",
            "step_status": StepStatus.SUCCESS,
        },
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.RUNNING,
            "last_step": "immediate step",
            "step_status": StepStatus.SUCCESS,
        },
        {
            "assignee": Assignee.SYSTEM,
            "status": ProcessStatus.COMPLETED,
            "last_step": "Done",
            "step_status": StepStatus.COMPLETE,
        },
    ]

    test_workflow_1_messages = []
    test_workflow_2_messages = []

    try:
        with test_client.websocket_connect("api/processes/all/?token=") as websocket:
            # start test_workflow
            test_workflow_response = test_client.post(f"/api/processes/{test_workflow.name}", json=[{}])

            assert (
                test_workflow_response.status_code == HTTPStatus.CREATED
            ), f"Invalid response status code (response data: {test_workflow_response.json()})"

            test_workflow_1_pid = test_workflow_response.json()["id"]

            # Start test_workflow_2
            response = test_client.post(f"/api/processes/{test_workflow_2.name}", json=[{}])
            assert (
                response.status_code == HTTPStatus.CREATED
            ), f"Invalid response status code (response data: {response.json()})"

            test_workflow_2_pid = response.json()["id"]

            # Make sure it started again
            time.sleep(1)

            # close and call receive_text to check websocket close exception
            websocket.close()

            # Checks if the correct messages are send, without order for which workflow.
            while True:
                if message_count == 9:
                    break
                message = websocket.receive_text()
                message_count += 1
                json_data = json_loads(message)
                assert "process" in json_data, f"Websocket message does not contain process: {json_data}"
                process_id = json_data["process"]["process_id"]

                if process_id == test_workflow_1_pid:
                    test_workflow_1_messages.append(json_data)
                elif process_id == test_workflow_2_pid:
                    test_workflow_2_messages.append(json_data)
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE
    except AssertionError as e:
        raise e

    assert message_count == 9

    for index, message in enumerate(test_workflow_1_messages):
        process = message["process"]
        expectedData = expected_workflow_1_steps.pop(0)

        assert process["assignee"] == expectedData["assignee"]
        assert process["last_status"] == expectedData["status"]

        assert process["last_step"] == expectedData["last_step"]
        assert process["steps"][index]["name"] == expectedData["last_step"]
        assert process["steps"][index]["status"] == expectedData["step_status"]

    for index, message in enumerate(test_workflow_2_messages):
        process = message["process"]
        expectedData = expected_workflow_2_steps.pop(0)

        assert process["assignee"] == expectedData["assignee"]
        assert process["last_status"] == expectedData["status"]

        assert process["last_step"] == expectedData["last_step"]
        assert process["steps"][index]["name"] == expectedData["last_step"]
        assert process["steps"][index]["status"] == expectedData["step_status"]

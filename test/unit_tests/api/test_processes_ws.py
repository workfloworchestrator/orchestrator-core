import time
from collections.abc import Generator
from http import HTTPStatus
from threading import Condition
from typing import Any
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.websockets import WebSocketDisconnect

from orchestrator.db import ProcessStepTable, ProcessSubscriptionTable, ProcessTable, db
from orchestrator.settings import app_settings
from orchestrator.types import UUIDstr
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


# long-running workflow test only works locally and with memory type
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
        with test_client.websocket_connect("api/ws/events") as websocket:
            # Check the websocket publishes correct process cache invalidation messages.

            # Let first long step finish, receive_json would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(2)

            expected_cache_invalidation_messages = [
                {"name": "invalidateCache", "value": {"type": "processes", "id": "LIST"}},
                {"name": "invalidateCache", "value": {"type": "processes", "id": str(process_id)}},
            ]

            def get_ws_messages():
                return [websocket.receive_json(), websocket.receive_json()]

            # messages step 1.
            assert get_ws_messages() == expected_cache_invalidation_messages

            # message step 2.
            assert get_ws_messages() == expected_cache_invalidation_messages

            # Let second long step finish, receive_json would otherwise wait for a message indefinitely.
            with test_condition:
                test_condition.notify_all()
            time.sleep(1)

            # message step 3.
            assert get_ws_messages() == expected_cache_invalidation_messages

            # message step 4.
            assert get_ws_messages() == expected_cache_invalidation_messages

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
        with test_client.websocket_connect("api/ws/events") as websocket:
            # Resume process
            user_input = {"generic_select": "A"}

            response = test_client.put(f"/api/processes/{process_id}/resume", json=[user_input])
            assert HTTPStatus.NO_CONTENT == response.status_code

            def get_ws_messages():
                return [websocket.receive_json(), websocket.receive_json()]

            expected_cache_invalidation_messages = [
                {"name": "invalidateCache", "value": {"type": "processes", "id": "LIST"}},
                {"name": "invalidateCache", "value": {"type": "processes", "id": str(process_id)}},
            ]

            assert get_ws_messages() == expected_cache_invalidation_messages

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
        with test_client.websocket_connect("api/ws/events") as websocket:
            # Abort process
            response = test_client.put(f"/api/processes/{process_id}/abort")
            assert HTTPStatus.NO_CONTENT == response.status_code

            def get_ws_messages():
                return [websocket.receive_json(), websocket.receive_json()]

            expected_cache_invalidation_messages = [
                {"name": "invalidateCache", "value": {"type": "processes", "id": "LIST"}},
                {"name": "invalidateCache", "value": {"type": "processes", "id": str(process_id)}},
            ]

            assert get_ws_messages() == expected_cache_invalidation_messages

            # close and call receive_text to check websocket close exception
            websocket.close()
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE


def test_websocket_process_list_multiple_workflows(test_client, test_workflow, test_workflow_2):  # noqa: C901
    # This tests the ProcessDataBroadcastThread as well
    if websocket_manager.broadcaster_type != "memory":
        pytest.skip("test does not work with redis")

    # to keep track of the amount of websocket messages
    message_count = 0

    process_1_cache_invalidation_messages = []
    process_2_cache_invalidation_messages = []
    list_invalidation_messages = []

    try:
        with test_client.websocket_connect("api/ws/events") as websocket:
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

            num_wf1_steps = 4  # 4 steps, then suspend
            num_wf2_steps = 5

            num_ws_messages = (num_wf1_steps + num_wf2_steps) * 2  # 2 messages per completed step

            # Checks if the correct messages are send, without order for which workflow.
            while True:
                if message_count == num_ws_messages:
                    break
                json_data = websocket.receive_json()
                message_count += 1
                assert "value" in json_data, f"Websocket message does not contain key 'value': {json_data}"
                process_id = json_data["value"]["id"]

                if process_id == test_workflow_1_pid:
                    process_1_cache_invalidation_messages.append(json_data)
                elif process_id == test_workflow_2_pid:
                    process_2_cache_invalidation_messages.append(json_data)
                else:
                    list_invalidation_messages.append(json_data)
    except WebSocketDisconnect as exception:
        assert exception.code == status.WS_1000_NORMAL_CLOSURE
    except AssertionError as e:
        raise e

    assert message_count == num_ws_messages

    for message in process_1_cache_invalidation_messages:
        assert message == {"name": "invalidateCache", "value": {"type": "processes", "id": test_workflow_1_pid}}

    assert len(process_1_cache_invalidation_messages) == num_wf1_steps

    for message in process_2_cache_invalidation_messages:
        assert message == {"name": "invalidateCache", "value": {"type": "processes", "id": test_workflow_2_pid}}

    assert len(process_2_cache_invalidation_messages) == num_wf2_steps

    for message in list_invalidation_messages:
        assert message == {"name": "invalidateCache", "value": {"type": "processes", "id": "LIST"}}

    assert len(list_invalidation_messages) == num_wf1_steps + num_wf2_steps

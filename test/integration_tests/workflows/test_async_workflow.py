# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import timedelta

from orchestrator.core.db import ProcessTable, db
from orchestrator.core.services import processes
from orchestrator.core.targets import Target
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import (
    CALLBACK_TIMEOUT_KEY,
    DEFAULT_CALLBACK_PROGRESS_KEY,
    DEFAULT_CALLBACK_ROUTE_KEY,
    AwaitingCallback,
    ProcessStatus,
    begin,
    callback_step,
    done,
    runwf,
    step,
    workflow,
)
from test.integration_tests.workflows import (
    WorkflowInstanceForTests,
    _store_step,
    assert_awaiting_callback,
    assert_complete,
    assert_state,
    run_workflow,
)


def _backdate_await_step(process_id: str, seconds: int) -> None:
    """Move the awaiting step's started_at into the past so its timeout is considered elapsed."""
    process = db.session.get(ProcessTable, process_id)
    assert process is not None
    await_step = process.steps[-1]
    await_step.started_at = nowtz() - timedelta(seconds=seconds)
    db.session.add(await_step)
    db.session.commit()


@step("Step 1")
def step1():
    return {"steps": [1]}


@step("Step 2")
def step2(steps):
    return {"steps": [*steps, 2]}


@step("Action")
def action():
    return {"ext_response": "Request received"}


@step("Action - Dry run")
def action_dr():
    return {"phase": "DRY_RUN"}


@step("Action - For real")
def action_fr():
    return {"phase": "FOR_REAL"}


@step("Validate")
def validate_state(phase, callback_result):
    if not callback_result["ext_data"].isnumeric():
        raise ValueError("ext_data must be numeric")
    if phase == "DRY_RUN":
        return {"dr_ext_data": callback_result["ext_data"]}
    if phase == "FOR_REAL":
        return {"ext_data": callback_result["ext_data"]}
    raise AssertionError(f"Unknown phase: {phase}")


@step("Cleanup")
def cleanup():
    return {"phase": None}


cb1 = callback_step("Dry run", action_step=action_dr, validate_step=validate_state)
cb2 = callback_step("For real", action_step=action_fr, validate_step=validate_state)


@workflow(target=Target.CREATE)
def multiple_callback_wf():
    return begin >> cb1 >> cb2 >> cleanup >> done


def test_workflow_with_callback():
    @step("Validate")
    def validate(code):
        if code != "12345":
            raise ValueError("Response code is wrong")
        return {"status": "ok"}

    call_ext_system = callback_step(name="Call ext system", action_step=action, validate_step=validate)

    @workflow(target=Target.CREATE)
    def test_wf():
        return begin >> step1 >> call_ext_system >> step2 >> done

    with WorkflowInstanceForTests(test_wf, "test_wf"):
        result, process, step_log = run_workflow("test_wf", {})
        assert_awaiting_callback(result)
        state = result.unwrap()
        assert DEFAULT_CALLBACK_ROUTE_KEY in state
        assert state.get("__sub_step") == "Call ext system - Await callback"

        step_log = [step_log[0]] + [step_log[-1]]

        process = process.update(log=process.workflow.steps[1:], state=AwaitingCallback({**state, "code": "12345"}))
        result = runwf(process, _store_step(step_log))
        assert_complete(result)
        assert_state(result, {"steps": [1, 2], "code": "12345"})


def test_callback_wf_with_custom_callback_route():
    call_ext_system = callback_step(
        name="Call ext system", action_step=action, validate_step=step1, callback_route_key="custom_route_key"
    )

    @workflow(target=Target.CREATE)
    def test_wf():
        return begin >> call_ext_system >> done

    with WorkflowInstanceForTests(test_wf, "test_wf"):
        result, process, step_log = run_workflow("test_wf", {})
        assert_awaiting_callback(result)
        state = result.unwrap()
        assert DEFAULT_CALLBACK_ROUTE_KEY not in state
        assert "custom_route_key" in state


def test_wf_with_multiple_callback_steps(test_client):
    with WorkflowInstanceForTests(multiple_callback_wf, "multiple_callback_wf"):
        # Start workflow
        response = test_client.post("/api/processes/multiple_callback_wf", json=[{}])
        assert response.status_code == 201
        process_id = response.json()["id"]

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        assert response_data["last_status"] == "awaiting_callback"
        state = response_data["current_state"]
        assert state["phase"] == "DRY_RUN"
        assert state["__step_group"] == "Dry run"
        assert state["__sub_step"] == "Dry run - Await callback"
        assert "callback_route" in state

        # Continue workflow 1
        callback_route1 = state["callback_route"]
        response = test_client.post(callback_route1, json={"ext_data": "12345", "other": "useless data"})
        assert response.status_code == 200

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        assert response_data["last_status"] == "awaiting_callback"
        state = response_data["current_state"]
        assert state["dr_ext_data"] == "12345"
        assert state["phase"] == "FOR_REAL"
        assert state["__step_group"] == "For real"
        assert state["__sub_step"] == "For real - Await callback"
        assert "callback_route" in state

        callback_route2 = state["callback_route"]

        assert callback_route1 != callback_route2, "Randomly generated callback routes should be distinct"

        # Continue workflow 2
        response = test_client.post(callback_route2, json={"ext_data": "56789", "other": "very useful data"})
        assert response.status_code == 200

        # Final check
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()

        assert response_data["last_status"] == "completed"

        state = response_data["current_state"]
        assert state["ext_data"] == "56789"

        assert state["phase"] is None


def test_wf_callback_progress_on_completed_process(test_client):
    # given
    @workflow(target=Target.CREATE)
    def test_wf():
        return begin >> step1 >> done

    with WorkflowInstanceForTests(test_wf, "test_wf"):
        response = test_client.post("/api/processes/test_wf", json=[{}])
        assert response.status_code == 201
        process_id = response.json()["id"]

        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        assert response_data["last_status"] == "completed"

        # when
        response = test_client.post(f"api/processes/{process_id}/callback/token123/progress", json={})
        response_data = response.json()

        # then
        assert response.status_code == 409
        assert response_data["detail"] == "This process is not in an awaiting state."


def test_wf_callback_progress_with_incorrect_token(test_client):
    # given
    @workflow(target=Target.CREATE)
    def test_wf():
        return begin >> cb1 >> done

    with WorkflowInstanceForTests(test_wf, "test_wf"):
        response = test_client.post("/api/processes/test_wf", json=[{}])
        assert response.status_code == 201
        process_id = response.json()["id"]

        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        assert response_data["last_status"] == "awaiting_callback"

        # when
        response = test_client.post(f"api/processes/{process_id}/callback/incorrectoken/progress", json={})
        response_data = response.json()

        # then
        assert response.status_code == 404
        assert response_data["detail"] == "Invalid token"


def test_wf_callback_progress_with_multiple_callback_steps(test_client):
    with WorkflowInstanceForTests(multiple_callback_wf, "multiple_callback_wf"):
        # Start workflow
        response = test_client.post("/api/processes/multiple_callback_wf", json=[{}])
        assert response.status_code == 201
        process_id = response.json()["id"]

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        assert response_data["last_status"] == "awaiting_callback"
        state = response_data["current_state"]

        # Update dry step progress with dict - update 1
        callback_route1 = state["callback_route"]
        response = test_client.post(
            f"{callback_route1}/progress",
            json={"update": 1},
        )
        assert response.status_code == 200
        response_data = response.json()

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        state = response_data["current_state"]
        assert state[DEFAULT_CALLBACK_PROGRESS_KEY] == {"update": 1}

        # Update dry step progress with dict - update 2
        callback_route1 = state["callback_route"]
        response = test_client.post(
            f"{callback_route1}/progress",
            json={"update": 2},
        )
        assert response.status_code == 200
        response_data = response.json()

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        state = response_data["current_state"]
        assert state[DEFAULT_CALLBACK_PROGRESS_KEY] == {"update": 2}

        # Continue workflow dry step
        callback_route1 = state["callback_route"]
        response = test_client.post(callback_route1, json={"ext_data": "12345"})
        assert response.status_code == 200

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        assert response_data["last_status"] == "awaiting_callback"
        state = response_data["current_state"]
        assert state["dr_ext_data"] == "12345"
        assert DEFAULT_CALLBACK_PROGRESS_KEY not in state

        # Update real step progress with string - update 1
        callback_route2 = state["callback_route"]
        response = test_client.post(
            f"{callback_route2}/progress", data="update 1", headers={"Content-Type": "text/plain; charset=utf-8"}
        )
        assert response.status_code == 200
        response_data = response.json()

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        state = response_data["current_state"]
        assert state[DEFAULT_CALLBACK_PROGRESS_KEY] == "update 1"

        # Update real step progress with string - update 2
        callback_route2 = state["callback_route"]
        response = test_client.post(
            f"{callback_route2}/progress", data="update 2", headers={"Content-Type": "text/plain; charset=utf-8"}
        )
        assert response.status_code == 200
        response_data = response.json()

        # Check process status
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        state = response_data["current_state"]
        assert state[DEFAULT_CALLBACK_PROGRESS_KEY] == "update 2"

        # Continue workflow real step
        response = test_client.post(callback_route2, json={"ext_data": "56789"})
        assert response.status_code == 200

        # Final check
        response = test_client.get(f"api/processes/{process_id}")
        response_data = response.json()
        state = response_data["current_state"]

        assert response_data["last_status"] == "completed"

        assert all(
            key in state.keys()
            for key in [
                "phase",
                "ext_data",
                "reporter",
                "process_id",
                "dr_ext_data",
                "workflow_name",
                "callback_route",
                "callback_result",
                "workflow_target",
            ]
        )

        state = response_data["current_state"]
        assert state["ext_data"] == "56789"
        assert DEFAULT_CALLBACK_PROGRESS_KEY not in state


def _start_timeout_wf(test_client, timeout):
    call_ext = callback_step(name="Call ext", action_step=action, validate_step=step1, timeout=timeout)

    @workflow(target=Target.CREATE)
    def timeout_wf():
        return begin >> step1 >> call_ext >> done

    instance = WorkflowInstanceForTests(timeout_wf, "timeout_wf")
    instance.__enter__()
    response = test_client.post("/api/processes/timeout_wf", json=[{}])
    assert response.status_code == 201
    process_id = response.json()["id"]
    assert test_client.get(f"api/processes/{process_id}").json()["last_status"] == "awaiting_callback"
    return instance, process_id


def test_callback_step_timeout_stored_in_state(test_client):
    instance, process_id = _start_timeout_wf(test_client, timeout=300)
    try:
        process = db.session.get(ProcessTable, process_id)
        assert process.steps[-1].state[CALLBACK_TIMEOUT_KEY] == 300
    finally:
        instance.__exit__(None, None, None)


def test_callback_step_without_timeout_has_no_timeout_key(test_client):
    instance, process_id = _start_timeout_wf(test_client, timeout=None)
    try:
        process = db.session.get(ProcessTable, process_id)
        assert CALLBACK_TIMEOUT_KEY not in process.steps[-1].state
    finally:
        instance.__exit__(None, None, None)


def test_timed_out_callback_fails_in_place_and_can_be_retried(test_client):
    instance, process_id = _start_timeout_wf(test_client, timeout=300)
    try:
        steps_before = len(db.session.get(ProcessTable, process_id).steps)
        _backdate_await_step(process_id, seconds=600)

        processes.fail_awaiting_process(db.session.get(ProcessTable, process_id))

        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.FAILED
        assert process.failed_reason == "Callback timed out"
        # In-place: the awaiting row turned FAILED, no orphan extra row was appended.
        assert len(process.steps) == steps_before
        assert process.steps[-1].name == "Call ext"

        # Retry re-runs the callback group (re-issues the action) and waits again.
        response = test_client.put(f"/api/processes/{process_id}/resume", json=[{}])
        assert response.status_code == 204
        assert test_client.get(f"api/processes/{process_id}").json()["last_status"] == "awaiting_callback"
    finally:
        instance.__exit__(None, None, None)


def test_timed_out_callback_can_be_aborted(test_client):
    instance, process_id = _start_timeout_wf(test_client, timeout=300)
    try:
        _backdate_await_step(process_id, seconds=600)
        processes.fail_awaiting_process(db.session.get(ProcessTable, process_id))

        response = test_client.put(f"/api/processes/{process_id}/abort")
        assert response.status_code == 204
        assert test_client.get(f"api/processes/{process_id}").json()["last_status"] == "aborted"
    finally:
        instance.__exit__(None, None, None)


def test_sweep_selection_respects_the_deadline(test_client):
    # The sweep only fails processes _is_timed_out selects; a process still within its window is not picked.
    from orchestrator.core.workflows.tasks.validate_awaiting_callbacks import _is_timed_out

    instance, process_id = _start_timeout_wf(test_client, timeout=300)
    try:
        _backdate_await_step(process_id, seconds=60)  # within the 300s window
        assert _is_timed_out(db.session.get(ProcessTable, process_id), nowtz()) is False

        _backdate_await_step(process_id, seconds=600)  # past the 300s window
        assert _is_timed_out(db.session.get(ProcessTable, process_id), nowtz()) is True
    finally:
        instance.__exit__(None, None, None)


def test_fail_awaiting_process_is_noop_when_not_awaiting(test_client):
    # Concurrency guard: if the callback already arrived (process no longer awaiting), failing is a no-op.
    @workflow(target=Target.CREATE)
    def plain_wf():
        return begin >> step1 >> done

    with WorkflowInstanceForTests(plain_wf, "plain_wf"):
        response = test_client.post("/api/processes/plain_wf", json=[{}])
        process_id = response.json()["id"]
        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.COMPLETED

        result = processes.fail_awaiting_process(process)

        assert result.iscomplete()
        assert db.session.get(ProcessTable, process_id).last_status == ProcessStatus.COMPLETED

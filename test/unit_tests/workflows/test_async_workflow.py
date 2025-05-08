from orchestrator.targets import Target
from orchestrator.workflow import (
    DEFAULT_CALLBACK_PROGRESS_KEY,
    DEFAULT_CALLBACK_ROUTE_KEY,
    AwaitingCallback,
    begin,
    callback_step,
    done,
    runwf,
    step,
    workflow,
)
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
    _store_step,
    assert_awaiting_callback,
    assert_complete,
    assert_state,
    run_workflow,
)


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


@workflow("Multiple callback wf", target=Target.CREATE)
def multiple_callback_wf():
    return begin >> cb1 >> cb2 >> cleanup >> done


def test_workflow_with_callback():
    @step("Validate")
    def validate(code):
        if code != "12345":
            raise ValueError("Response code is wrong")
        return {"status": "ok"}

    call_ext_system = callback_step(name="Call ext system", action_step=action, validate_step=validate)

    @workflow("Test wf", target=Target.CREATE)
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

    @workflow("Test wf", target=Target.CREATE)
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
    @workflow("Test wf", target=Target.CREATE)
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
    @workflow("Test wf", target=Target.CREATE)
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

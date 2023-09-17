from orchestrator.types import State
from orchestrator.workflow import AwaitingCallback, begin, callback_step, done, runwf, step, workflow
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


def test_workflow_with_callback():
    def action_fn() -> State:
        return {"ext_response": "Request received"}

    def validate_fn(state: State) -> State:
        code = state.get("code")
        if code != "12345":
            raise ValueError("Response code is wrong")
        return {"status": "ok"}

    call_ext_system = callback_step(name="Call ext system", action_fn=action_fn, validate_fn=validate_fn)

    @workflow("Test wf", target="Target.CREATE")
    def testwf():
        return begin >> step1 >> call_ext_system >> step2 >> done

    with WorkflowInstanceForTests(testwf, "testwf"):
        result, process, step_log = run_workflow("testwf", {})
        assert_awaiting_callback(result)
        state = result.unwrap()
        assert "callback_route" in state
        assert state.get("__sub_step") == "Call ext system - Await callback"

        step_log = [step_log[0]] + [step_log[-1]]

        process = process.update(log=process.workflow.steps[1:], state=AwaitingCallback({**state, "code": "12345"}))
        result = runwf(process, _store_step(step_log))
        assert_complete(result)
        assert_state(result, {"steps": [1, 2], "code": "12345"})


def test_callback_wf_with_custom_callback_route():
    def action_fn() -> State:
        return {"ext_response": "Request received"}

    def validate_fn() -> State:
        return {}

    call_ext_system = callback_step(
        name="Call ext system", action_fn=action_fn, validate_fn=validate_fn, callback_route_key="custom_route_key"
    )

    @workflow("Test wf", target="Target.CREATE")
    def testwf():
        return begin >> call_ext_system >> done

    with WorkflowInstanceForTests(testwf, "testwf"):
        result, process, step_log = run_workflow("testwf", {})
        assert_awaiting_callback(result)
        state = result.unwrap()
        assert "callback_route" not in state
        assert "custom_route_key" in state

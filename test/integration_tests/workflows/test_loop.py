# Copyright 2026 NOMIOS.
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

from uuid import uuid4

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.services.processes import SYSTEM_USER
from orchestrator.core.targets import Target
from orchestrator.core.workflow import (
    ProcessStat,
    StepList,
    Success,
    begin,
    done,
    init,
    inputstep,
    loop,
    runwf,
    step,
    workflow,
)
from pydantic_forms.core import FormPage
from test.integration_tests.workflows import (
    WorkflowInstanceForTests,
    assert_complete,
    assert_failed,
    assert_state,
    assert_suspended,
    resume_workflow,
    run_workflow,
)
from test.integration_tests.workflows.test_workflow import store


def create_new_process_stat(workflow, initial_state):
    return ProcessStat(
        process_id=str(uuid4()),
        workflow=workflow,
        state=Success(initial_state),
        log=workflow.steps,
        current_user=SYSTEM_USER,
    )


@step("Increment counter")
def increment_counter_step(counter=0):
    return {"counter": counter + 1}


def _counter_at_least_three(state):
    return state.get("counter", 0) >= 3


def test_loop_static_body():
    """A static StepList body runs repeatedly until `until` fires."""
    lp = loop("Counter loop", begin >> increment_counter_step, until=_counter_at_least_three)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_complete(result)
    assert_state(result, {"counter": 3})


def test_loop_dynamic_body():
    """A callable body is invoked per-iteration with (state, iteration)."""
    seen_iterations = []

    @step("Increment counter (dynamic)")
    def dynamic_increment_counter(counter=0):
        return {"counter": counter + 1}

    def build(state, iteration):
        seen_iterations.append(iteration)
        return begin >> dynamic_increment_counter

    lp = loop("Dynamic loop", build, until=_counter_at_least_three)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_complete(result)
    assert_state(result, {"counter": 3})
    assert seen_iterations == [0, 1, 2]


def test_loop_limit_reached_raises():
    lp = loop("Never done loop", begin >> increment_counter_step, until=lambda s: False, limit=2)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_failed(result)
    error = result.unwrap()
    assert error["class"] == "LoopLimitReached"
    assert "limit of 2" in error["error"]


def test_loop_records_loop_steps():
    lp = loop("Recorded loop", begin >> increment_counter_step, until=_counter_at_least_three)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_complete(result)
    loop_steps = result.unwrap()["loop_steps"]
    assert [entry["name"] for entry in loop_steps] == ["step_0_0", "step_1_0", "step_2_0"]
    assert all(entry["status"] == "success" for entry in loop_steps)


@inputstep("Approve", assignee=Assignee.SYSTEM)
def approve_step() -> type[FormPage]:
    class Form(FormPage):
        raw_approved: bool

    return Form


@step("Record approval")
def record_approval(raw_approved):
    # `until` is gated on `approved`, a key only this step sets, so the loop's exit predicate can't
    # be satisfied purely by the form input merged in on resume -- the rest of the iteration's steps
    # (this step) must actually run first.
    return {"approved": raw_approved}


def _approved(state):
    return state.get("approved") is True


def test_loop_resume_mid_iteration():
    """An inner @inputstep suspends the loop; resuming continues the same iteration."""
    lp = loop("Approval loop", begin >> approve_step >> record_approval, until=_approved)

    @workflow(target=Target.CREATE)
    def approval_wf():
        return init >> lp >> done

    with WorkflowInstanceForTests(approval_wf, "approval_wf"):
        result, process, step_log = run_workflow("approval_wf", {})
        assert_suspended(result)
        assert result.unwrap()["__sub_step"] == "step_0_0"

        resume_result, step_log = resume_workflow(process, step_log, {"raw_approved": True})

        assert_complete(resume_result)
        assert_state(resume_result, {"approved": True})
        loop_steps = resume_result.unwrap()["loop_steps"]
        assert [entry["name"] for entry in loop_steps] == ["step_0_0", "step_0_1"]
        assert loop_steps[0]["was_suspended"] is True
        assert loop_steps[0]["status"] == "success"


def test_loop_resume_across_iterations():
    """Looping back for a second approval spans iterations; sub-step names carry the iteration index."""
    lp = loop("Multi-round approval loop", begin >> approve_step >> record_approval, until=_approved)

    @workflow(target=Target.CREATE)
    def approval_wf():
        return init >> lp >> done

    with WorkflowInstanceForTests(approval_wf, "approval_wf_multi"):
        result, process, step_log = run_workflow("approval_wf_multi", {})
        assert_suspended(result)
        assert result.unwrap()["__sub_step"] == "step_0_0"

        rejected_result, step_log = resume_workflow(process, step_log, {"raw_approved": False})
        assert_suspended(rejected_result)
        assert rejected_result.unwrap()["__sub_step"] == "step_1_0"

        approved_result, step_log = resume_workflow(process, step_log, {"raw_approved": True})

        assert_complete(approved_result)
        loop_steps = approved_result.unwrap()["loop_steps"]
        assert [entry["name"] for entry in loop_steps] == [
            "step_0_0",
            "step_0_1",
            "step_1_0",
            "step_1_1",
        ]


def test_loop_records_an_entry_for_every_step():
    """Every step in an iteration gets its own loop_steps entry; there is no way to opt out."""

    @step("Visible")
    def visible_step(counter=0):
        return {"counter": counter + 1}

    @step("Plumbing")
    def plumbing_step():
        return {"plumbing_ran": True}

    lp = loop("Loop with two steps", begin >> visible_step >> plumbing_step, until=_counter_at_least_three)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_complete(result)
    assert result.unwrap()["plumbing_ran"] is True
    loop_steps = result.unwrap()["loop_steps"]
    assert [entry["name"] for entry in loop_steps] == [
        "step_0_0",
        "step_0_1",
        "step_1_0",
        "step_1_1",
        "step_2_0",
        "step_2_1",
    ]


class RecoverableError(Exception):
    pass


@step("Maybe fail")
def maybe_fail():
    raise RecoverableError("boom")


@step("Never reached")
def never_reached():
    return {"never_reached": True}


@step("Recovered")
def recovered_step(counter=0):
    return {"counter": counter + 1}


def _counter_at_least_one(state):
    return state.get("counter", 0) >= 1


def test_loop_on_error_recovery_and_abandoned_branch():
    """on_error can replace the rest of a failed iteration; abandoned entries move to loop_steps_branches."""

    def build(state, iteration):
        return begin >> maybe_fail >> never_reached

    def on_error(error, iteration_start_state):
        if error.get("class") != "RecoverableError":
            return None
        return StepList([recovered_step])

    lp = loop("Recovering loop", build, until=_counter_at_least_one, on_error=on_error, limit=5)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_complete(result)
    assert_state(result, {"counter": 1})
    assert "never_reached" not in result.unwrap()

    state = result.unwrap()
    branches = state["loop_steps_branches"]
    assert branches, "expected at least one abandoned branch to be recorded"
    abandoned = branches["0"]
    # The failed step itself (kept for context) plus the never-run step queued after it.
    assert [entry["name"] for entry in abandoned] == ["step_0_0", "step_0_1"]
    assert abandoned[0]["status"] == "failed"
    assert abandoned[1]["status"] == "pending"

    # The trunk only ever sees the recovery's own entry -- the failed attempt's entries were cut away.
    loop_steps = state["loop_steps"]
    assert [entry["name"] for entry in loop_steps] == ["step_0_0"]
    assert loop_steps[0]["status"] == "success"


def test_loop_on_error_recovery_state_stripped_on_resume():
    """on_error's state argument differs by call site.

    It's the full state on the initial call, but a stripped snapshot (no `__`-prefixed keys, no
    loop_steps/loop_steps_branches) when loop calls on_error again to regenerate a recovery step
    that itself suspended.
    """
    seen_states = []

    @step("Always fails")
    def always_fails():
        raise RecoverableError("boom")

    @inputstep("Confirm recovery", assignee=Assignee.SYSTEM)
    def confirm_recovery() -> type[FormPage]:
        class Form(FormPage):
            confirmed: bool

        return Form

    def on_error(error, iteration_start_state):
        seen_states.append(iteration_start_state)
        if error.get("class") != "RecoverableError":
            return None
        return StepList([confirm_recovery])

    # `until` never fires, so the only way this loop step resolves is via the recovery step's own
    # @inputstep suspend -- there is no second iteration to reason about.
    lp = loop("Loop with suspending recovery", begin >> always_fails, until=lambda s: False, on_error=on_error, limit=5)

    @workflow(target=Target.CREATE)
    def suspending_recovery_wf():
        return init >> lp >> done

    with WorkflowInstanceForTests(suspending_recovery_wf, "suspending_recovery_wf"):
        result, process, step_log = run_workflow("suspending_recovery_wf", {})
        assert_suspended(result)

        # Resuming re-derives the suspended recovery step (to look up its form), which calls
        # on_error a second time. The recovered iteration's `always_fails` step fires again on the
        # next iteration, so the loop simply suspends again; that's fine, we only need one resume.
        resume_result, step_log = resume_workflow(process, step_log, {"confirmed": True})
        assert_suspended(resume_result)

    # Calls triggered by a live failure (the first iteration's, and the second iteration's after
    # resume) see the full state, including internal bookkeeping keys.
    live_failure_calls = [seen_states[0], seen_states[-1]]
    for full_state in live_failure_calls:
        assert "process_id" in full_state
        assert any(k.startswith("__") for k in full_state)

    # Calls in between are `loop` re-deriving the suspended recovery step (to resolve its form) by
    # calling on_error again with the stripped snapshot recorded on the body descriptor, not the
    # live state.
    replay_calls = seen_states[1:-1]
    assert replay_calls, "expected at least one on_error replay call while resolving the suspended recovery step"
    for stripped_state in replay_calls:
        assert not any(k.startswith("__") for k in stripped_state)
        assert "loop_steps" not in stripped_state
        assert "loop_steps_branches" not in stripped_state


def test_loop_on_error_returns_none_propagates_failure():
    """When on_error declines to handle an error (returns None), the loop step fails as normal."""

    @step("Always fails")
    def always_fails():
        raise RecoverableError("boom")

    def on_error(error, iteration_start_state):
        return None

    lp = loop("Non-recovering loop", begin >> always_fails, until=lambda s: False, on_error=on_error)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_failed(result)


class OnErrorBugError(Exception):
    pass


def test_loop_on_error_raising_propagates_original_failure():
    """A bug in on_error itself (it raises) does not replace the original error it was handling."""

    @step("Always fails")
    def always_fails():
        raise RecoverableError("boom")

    def buggy_on_error(error, iteration_start_state):
        raise OnErrorBugError("bug in the handler")

    lp = loop("Loop with buggy handler", begin >> always_fails, until=lambda s: False, on_error=buggy_on_error)
    wf = workflow()(lambda: init >> lp >> done)

    log = []
    pstat = create_new_process_stat(wf, {})
    result = runwf(pstat, store(log))

    assert_failed(result)
    error = result.unwrap()
    # The failed loop step still carries the *original* error, not the handler's own exception.
    assert error["class"] == "RecoverableError"

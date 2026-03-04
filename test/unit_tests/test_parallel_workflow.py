"""Tests for parallel step execution in the workflow engine."""

from uuid import uuid4

import pytest

from orchestrator.config.assignee import Assignee
from orchestrator.services.processes import SYSTEM_USER
from orchestrator.workflow import (
    ParallelStepList,
    ProcessStat,
    Success,
    begin,
    conditional,
    done,
    init,
    inputstep,
    parallel,
    retrystep,
    runwf,
    step,
    step_group,
    workflow,
)
from pydantic_forms.core import FormPage
from test.unit_tests.workflows import (
    assert_complete,
    assert_failed,
    assert_waiting,
)

# --- Helpers ---


def create_new_process_stat(wf, initial_state):
    return ProcessStat(
        process_id=str(uuid4()),
        workflow=wf,
        state=Success(initial_state),
        log=wf.steps,
        current_user=SYSTEM_USER,
    )


def store(log):
    def _store(_pstat, step_, process):
        state = process.unwrap()
        step_name = state.pop("__step_name_override", step_.name)
        keys_to_remove = state.get("__remove_keys", []) + ["__remove_keys"]
        for k in keys_to_remove:
            state.pop(k, None)
        if state.pop("__replace_last_state", None):
            log[-1] = (step_name, process)
        else:
            log.append((step_name, process))
        return process

    return _store


# --- Step definitions for tests ---


@step("Branch A Step 1")
def branch_a_step1():
    return {"a1": "done"}


@step("Branch A Step 2")
def branch_a_step1_cont(a1):
    return {"a2": f"{a1}_continued"}


@step("Branch B Step 1")
def branch_b_step1():
    return {"b1": "done"}


@step("Branch B Step 2")
def branch_b_step1_cont(b1):
    return {"b2": f"{b1}_continued"}


@step("Sequential Before")
def seq_before():
    return {"before": True}


@step("Sequential After")
def seq_after(a1, b1, before):
    return {"after": True, "got_a1": a1, "got_b1": b1}


@retrystep("Retryable Branch Step")
def retryable_branch_step():
    raise ValueError("Retry me")


@step("Failing Branch Step")
def failing_branch_step():
    raise ValueError("Branch failed")


# --- Test: | operator and ParallelStepList ---


class TestPipeOperatorSyntax:
    """Test the | operator creates ParallelStepList correctly."""

    def test_pipe_creates_parallel_step_list(self):
        """StepList | StepList creates a ParallelStepList with 2 branches."""
        branch_a = begin >> branch_a_step1
        branch_b = begin >> branch_b_step1
        par = branch_a | branch_b

        assert isinstance(par, ParallelStepList)
        assert len(par.branches) == 2

    def test_pipe_chaining_creates_multiple_branches(self):
        """A | b | c creates a ParallelStepList with 3 branches."""
        branch_a = begin >> branch_a_step1
        branch_b = begin >> branch_b_step1

        @step("Branch C")
        def branch_c():
            return {"c1": "done"}

        par = branch_a | branch_b | (begin >> branch_c)
        assert isinstance(par, ParallelStepList)
        assert len(par.branches) == 3

    def test_pipe_operator_precedence_with_rshift(self):
        """>> binds tighter than |, so begin >> step_a | begin >> step_b works."""
        # This should parse as (begin >> branch_a_step1) | (begin >> branch_b_step1)
        par = begin >> branch_a_step1 | begin >> branch_b_step1

        assert isinstance(par, ParallelStepList)
        assert len(par.branches) == 2

    def test_unnamed_parallel_in_workflow(self):
        """| operator used directly in workflow definition with auto-generated name."""
        wf = workflow("Pipe WF")(lambda: init >> ((begin >> branch_a_step1) | (begin >> branch_b_step1)) >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"


class TestDictNamingSyntax:
    """Test the dict syntax for naming parallel blocks."""

    def test_dict_with_parallel_step_list(self):
        """{"name": branch_a | branch_b} creates a named parallel step."""
        wf = workflow("Dict WF")(
            lambda: init >> {"Provision ports": (begin >> branch_a_step1) | (begin >> branch_b_step1)} >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"

        # Verify the name appears in the log
        step_names = [entry[0] for entry in log]
        assert "Provision ports" in step_names

    def test_dict_with_list_of_steplists(self):
        """{"name": [branch_a, branch_b]} also works as alternative."""
        wf = workflow("Dict list WF")(
            lambda: init
            >> {
                "Provision ports": [
                    begin >> branch_a_step1,
                    begin >> branch_b_step1,
                ]
            }
            >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"

    def test_dict_with_multiple_keys_raises(self):
        """Dict with more than one key raises ValueError."""
        with pytest.raises(ValueError, match="exactly one key"):
            begin >> {
                "a": (begin >> branch_a_step1) | (begin >> branch_b_step1),
                "b": (begin >> branch_a_step1) | (begin >> branch_b_step1),
            }

    def test_dict_with_non_string_key_raises(self):
        """Dict with non-string key raises ValueError."""
        with pytest.raises(ValueError):
            begin >> {42: (begin >> branch_a_step1) | (begin >> branch_b_step1)}


# --- Test: Basic parallel execution ---


class TestParallelBasicExecution:
    """Test basic fork/join semantics."""

    def test_two_branches_merge_state(self):
        """Two branches execute and their states are merged."""
        wf = workflow("Parallel WF")(
            lambda: init
            >> seq_before
            >> {"Parallel block": (begin >> branch_a_step1) | (begin >> branch_b_step1)}
            >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["before"] is True
        assert state["a1"] == "done"
        assert state["b1"] == "done"

    def test_multi_step_branches(self):
        """Branches with multiple steps each execute fully."""
        wf = workflow("Parallel WF")(
            lambda: init
            >> ((begin >> branch_a_step1 >> branch_a_step1_cont) | (begin >> branch_b_step1 >> branch_b_step1_cont))
            >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["a2"] == "done_continued"
        assert state["b1"] == "done"
        assert state["b2"] == "done_continued"

    def test_three_branches(self):
        """Three or more branches work correctly."""

        @step("Branch C")
        def branch_c():
            return {"c1": "done"}

        wf = workflow("Triple WF")(
            lambda: init >> ((begin >> branch_a_step1) | (begin >> branch_b_step1) | (begin >> branch_c)) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"
        assert state["c1"] == "done"

    def test_sequential_after_parallel_sees_merged_state(self):
        """Steps after parallel block can access merged state from all branches."""
        wf = workflow("Parallel WF")(
            lambda: init
            >> seq_before
            >> {"Parallel block": (begin >> branch_a_step1) | (begin >> branch_b_step1)}
            >> seq_after
            >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["after"] is True
        assert state["got_a1"] == "done"
        assert state["got_b1"] == "done"


class TestParallelStateIsolation:
    """Test that branches receive isolated state copies."""

    def test_branches_dont_see_each_others_mutations(self):
        """Each branch gets a deep copy of state; mutations don't leak."""

        @step("Mutate shared key A")
        def mutate_a(shared_list):
            return {"result_a": len(shared_list), "a_list": [*shared_list, "a"]}

        @step("Mutate shared key B")
        def mutate_b(shared_list):
            return {"result_b": len(shared_list), "b_list": [*shared_list, "b"]}

        wf = workflow("Isolation WF")(lambda: init >> ((begin >> mutate_a) | (begin >> mutate_b)) >> done)

        log = []
        pstat = create_new_process_stat(wf, {"shared_list": [1, 2, 3]})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        # Both branches saw the original list of length 3
        assert state["result_a"] == 3
        assert state["result_b"] == 3


class TestParallelErrorHandling:
    """Test error handling in parallel branches."""

    def test_single_branch_failure_fails_group(self):
        """If one branch fails, the parallel group fails."""
        wf = workflow("Failing parallel WF")(
            lambda: init >> ((begin >> branch_a_step1) | (begin >> failing_branch_step)) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_failed(result)

    def test_retryable_branch_returns_waiting(self):
        """If one branch is retryable (Waiting), the parallel group returns Waiting."""
        wf = workflow("Retryable parallel WF")(
            lambda: init >> ((begin >> branch_a_step1) | (begin >> retryable_branch_step)) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_waiting(result)

    def test_failure_takes_precedence_over_waiting(self):
        """Failed status takes precedence over Waiting."""
        wf = workflow("Mixed error WF")(
            lambda: init >> ((begin >> retryable_branch_step) | (begin >> failing_branch_step)) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_failed(result)

    def test_steps_after_failed_parallel_not_executed(self):
        """Steps after a failed parallel block should not execute."""
        side_effects = []

        @step("Should not run")
        def should_not_run():
            side_effects.append("ran")
            return {}

        wf = workflow("WF")(
            lambda: init >> ((begin >> failing_branch_step) | (begin >> branch_a_step1)) >> should_not_run >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_failed(result)
        assert side_effects == [], "Step after failed parallel should not execute"


class TestParallelValidation:
    """Test validation of parallel() arguments."""

    def test_requires_at_least_two_branches(self):
        """parallel() with fewer than 2 branches raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 branches"):
            parallel("Single branch", begin >> branch_a_step1)

    def test_parallel_step_list_requires_two_branches(self):
        """ParallelStepList with fewer than 2 branches raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 branches"):
            ParallelStepList([begin >> branch_a_step1])

    def test_rejects_inputsteps_in_branches_via_parallel(self):
        """parallel() branches must not contain inputsteps."""

        @inputstep("User Input", assignee=Assignee.SYSTEM)
        def user_input() -> type[FormPage]:
            class Form(FormPage):
                name: str

            return Form

        with pytest.raises(ValueError, match="must not contain inputsteps"):
            parallel(
                "Invalid parallel",
                begin >> branch_a_step1,
                begin >> user_input,
            )

    def test_rejects_inputsteps_in_branches_via_pipe(self):
        """| operator with inputsteps raises ValueError when composed with >>."""

        @inputstep("User Input", assignee=Assignee.SYSTEM)
        def user_input() -> type[FormPage]:
            class Form(FormPage):
                name: str

            return Form

        with pytest.raises(ValueError, match="must not contain inputsteps"):
            # Validation happens when >> converts ParallelStepList to a Step
            begin >> ((begin >> branch_a_step1) | (begin >> user_input))


class TestParallelWithConditional:
    """Test parallel blocks with conditional steps."""

    def test_conditional_step_in_branch(self):
        """Conditional steps inside branches work correctly."""
        skip_b = conditional(lambda s: False)

        wf = workflow("Conditional parallel WF")(
            lambda: init >> ((begin >> branch_a_step1) | skip_b(branch_b_step1)) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"


class TestParallelComposition:
    """Test that parallel blocks compose with other workflow primitives."""

    def test_parallel_after_step_group(self):
        """Parallel block works after a step_group."""
        group = step_group("Group", begin >> branch_a_step1)

        @step("Independent C")
        def step_c():
            return {"c": True}

        wf = workflow("Composed WF")(lambda: init >> group >> ((begin >> branch_b_step1) | (begin >> step_c)) >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"  # from step_group
        assert state["b1"] == "done"  # from parallel branch 0
        assert state["c"] is True  # from parallel branch 1

    def test_multiple_parallel_blocks_in_sequence(self):
        """Multiple parallel blocks can appear in the same workflow."""

        @step("Step D")
        def step_d():
            return {"d": True}

        @step("Step E")
        def step_e():
            return {"e": True}

        wf = workflow("Multi parallel WF")(
            lambda: init
            >> ((begin >> branch_a_step1) | (begin >> branch_b_step1))
            >> ((begin >> step_d) | (begin >> step_e))
            >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"
        assert state["d"] is True
        assert state["e"] is True

    def test_parallel_function_still_works(self):
        """The explicit parallel() function continues to work for advanced use cases."""
        par = parallel("Explicit parallel", begin >> branch_a_step1, begin >> branch_b_step1)
        wf = workflow("Explicit WF")(lambda: init >> par >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"


class TestParallelBranchInputState:
    """Test that branches receive the correct input state."""

    def test_branches_receive_state_from_previous_step(self):
        """Each branch sees state produced by the step before the parallel block."""

        @step("Setup")
        def setup():
            return {"x": 42, "y": "hello"}

        @step("Use X")
        def use_x(x):
            return {"x_doubled": x * 2}

        @step("Use Y")
        def use_y(y):
            return {"y_upper": y.upper()}

        wf = workflow("Input state WF")(lambda: init >> setup >> ((begin >> use_x) | (begin >> use_y)) >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["x_doubled"] == 84
        assert state["y_upper"] == "HELLO"


class TestParallelStepLogging:
    """Test that parallel execution produces correct step logs."""

    def test_named_parallel_group_appears_in_log(self):
        """A named parallel group appears with its name in the step log."""
        wf = workflow("Logging WF")(
            lambda: init >> {"My parallel block": (begin >> branch_a_step1) | (begin >> branch_b_step1)} >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        step_names = [entry[0] for entry in log]
        assert "Start" in step_names
        assert "My parallel block" in step_names
        assert "Done" in step_names

    def test_unnamed_parallel_gets_auto_name_in_log(self):
        """An unnamed parallel group gets an auto-generated name in the step log."""
        wf = workflow("Logging WF")(lambda: init >> ((begin >> branch_a_step1) | (begin >> branch_b_step1)) >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        step_names = [entry[0] for entry in log]
        # Auto-generated name should contain the branch step names
        parallel_names = [n for n in step_names if "Parallel" in n or "Branch" in n]
        assert len(parallel_names) >= 1, f"Expected auto-named parallel step in log, got: {step_names}"


class TestParallelKeyConflictError:
    """Test that key conflicts between branches raise ValueError."""

    def test_conflicting_keys_raises_error(self):
        """Two branches writing to the same key raises ValueError."""

        @step("Write X from A")
        def write_x_a():
            return {"x": "from_a"}

        @step("Write X from B")
        def write_x_b():
            return {"x": "from_b"}

        wf = workflow("Conflict WF")(lambda: init >> ((begin >> write_x_a) | (begin >> write_x_b)) >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        # The ValueError from _join_results gets caught by the step execution and becomes Failed
        assert_failed(result)

    def test_non_conflicting_keys_succeed(self):
        """Two branches writing to different keys succeed."""
        wf = workflow("No conflict WF")(lambda: init >> ((begin >> branch_a_step1) | (begin >> branch_b_step1)) >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"

    def test_branches_can_read_same_keys_without_conflict(self):
        """Branches reading (but not modifying) the same upstream keys is fine."""

        @step("Read shared A")
        def read_shared_a(shared_val):
            return {"a_saw": shared_val}

        @step("Read shared B")
        def read_shared_b(shared_val):
            return {"b_saw": shared_val}

        @step("Setup shared")
        def setup_shared():
            return {"shared_val": 42}

        wf = workflow("Read shared WF")(
            lambda: init >> setup_shared >> ((begin >> read_shared_a) | (begin >> read_shared_b)) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a_saw"] == 42
        assert state["b_saw"] == 42

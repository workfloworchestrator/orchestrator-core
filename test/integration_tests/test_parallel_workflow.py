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

"""Tests for parallel step execution in the workflow engine.

Branch results are NOT merged into the main workflow state. After a parallel
block, the next step receives the pre-parallel (initial) state. Branch data
is persisted in the DB and accessible via ProcessStepRelationTable / child_steps.

TODO: move to the correct place in the integration tests (in the module of the main function being tested) or to acceptance tests
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from typing import cast
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import close_all_sessions, sessionmaker

import orchestrator.core.services.parallel as parallel_service
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import ProcessStepTable, ProcessTable, db
from orchestrator.core.db.database import SESSION_ARGUMENTS, BaseModel, SearchQuery
from orchestrator.core.db.models import ProcessStepRelationTable
from orchestrator.core.services.executors.types import ExecutorFunction
from orchestrator.core.services.parallel import _resolve_fork_step, run_worker_branch
from orchestrator.core.services.processes import SYSTEM_USER, create_process, load_process, safe_logstep
from orchestrator.core.settings import ExecutorType, app_settings
from orchestrator.core.testing import (
    WorkflowInstanceForTests,
    assert_complete,
    assert_failed,
    assert_waiting,
)
from orchestrator.core.testing.workflows import TEST_USER
from orchestrator.core.workflow import (
    BranchKind,
    ProcessStat,
    ProcessStatus,
    StepStatus,
    Success,
    _assert_parallel_step_is_visible,
    _child_step_lists,
    begin,
    callback_step,
    conditional,
    done,
    init,
    inputstep,
    map_parallel,
    parallel,
    process_stat_var,
    retrystep,
    runwf,
    step,
    step_group,
    workflow,
)
from pydantic_forms.core import FormPage


@pytest.fixture(autouse=True)
def db_session(database):
    """Use the engine's connection pool so each thread gets its own connection.

    The standard ``db_session`` fixture binds all sessions to a single shared
    connection wrapped in a rollback transaction. That approach breaks for
    parallel tests because multiple threads sharing one PostgreSQL connection
    causes savepoint conflicts.

    Instead, bind the session factory to the **engine** (connection pool).
    Each ``database_scope()`` in a branch thread obtains its own connection,
    matching production behaviour. Cleanup relies on ORM/DB cascades: when
    ``WorkflowInstanceForTests.__exit__`` deletes the workflow, all associated
    processes, steps, and relations are cascade-deleted.
    """
    db.wrapped_database.session_factory = sessionmaker(**SESSION_ARGUMENTS, bind=db.wrapped_database.engine)
    db.wrapped_database.scoped_session = scoped_session(db.session_factory, db._scopefunc)
    BaseModel.set_query(cast(SearchQuery, db.wrapped_database.scoped_session.query_property()))

    try:
        yield
    finally:
        close_all_sessions()


# --- Helpers ---

_wf_counter = 0


def register_test_workflow(wf):
    """Register a Workflow in the DB and return a context manager that cleans up on exit."""
    global _wf_counter
    _wf_counter += 1
    return WorkflowInstanceForTests(wf, f"test_parallel_wf_{_wf_counter}")


def create_new_process_stat(wf_table, initial_state):
    """Create a ProcessStat with a real DB-backed process.

    Args:
        wf_table: WorkflowTable instance (from WorkflowInstanceForTests context manager).
        initial_state: Initial workflow state dict.
    """
    from orchestrator.core.workflows import get_workflow

    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=wf_table.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
        is_task=wf_table.is_task,
    )
    db.session.add(p)
    db.session.commit()

    wf_obj = get_workflow(wf_table.name)
    return ProcessStat(
        process_id=process_id,
        workflow=wf_obj,
        state=Success(initial_state),
        log=wf_obj.steps,
        current_user=SYSTEM_USER,
    )


def store(log):
    def _store(_pstat, step_, process):
        state = process.unwrap()
        step_name = state.pop("__step_name_override", step_.name)
        for k in [*state.get("__remove_keys", []), "__remove_keys"]:
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


@retrystep("Retryable Branch Step")
def retryable_branch_step():
    raise ValueError("Retry me")


@step("Failing Branch Step")
def failing_branch_step():
    raise ValueError("Branch failed")


# --- Test: Dict naming syntax ---


def test_dict_with_list_of_steplists():
    """{"name": [branch_a, branch_b]} also works as alternative."""
    wf = workflow()(
        lambda: (
            init
            >> {
                "Provision ports": [
                    begin >> branch_a_step1,
                    begin >> branch_b_step1,
                ]
            }
            >> done
        )
    )

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "b1" not in state


def test_dict_with_multiple_keys_raises():
    """Dict with more than one key raises ValueError."""
    with pytest.raises(ValueError, match="exactly one key"):
        begin >> {
            "a": [begin >> branch_a_step1, begin >> branch_b_step1],
            "b": [begin >> branch_a_step1, begin >> branch_b_step1],
        }


def test_dict_with_non_string_key_raises():
    """Dict with non-string key raises ValueError."""
    with pytest.raises(ValueError):
        begin >> {42: [begin >> branch_a_step1, begin >> branch_b_step1]}


# --- Test: Basic parallel execution ---


def test_two_branches_pass_initial_state():
    """Two branches execute; post-parallel state is the pre-parallel state."""
    wf = workflow()(
        lambda: init >> seq_before >> {"Parallel block": [begin >> branch_a_step1, begin >> branch_b_step1]} >> done
    )

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert state["before"] is True
    assert "a1" not in state
    assert "b1" not in state


def test_multi_step_branches():
    """Branches with multiple steps each execute fully; state is not merged."""
    wf = workflow()(
        lambda: (
            init
            >> parallel(
                "branch a and b",
                begin >> branch_a_step1 >> branch_a_step1_cont,
                begin >> branch_b_step1 >> branch_b_step1_cont,
            )
            >> done
        )
    )

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "a2" not in state
    assert "b1" not in state
    assert "b2" not in state


def test_three_branches():
    """Three or more branches work correctly; state is not merged."""

    @step("Branch C")
    def branch_c():
        return {"c1": "done"}

    wf = workflow()(
        lambda: (
            init
            >> parallel("branch a b and c", begin >> branch_a_step1, begin >> branch_b_step1, begin >> branch_c)
            >> done
        )
    )

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "b1" not in state
    assert "c1" not in state


# --- Test: State isolation ---


def test_branches_dont_see_each_others_mutations():
    """Each branch gets a deep copy of state; mutations don't leak."""

    @step("Mutate shared key A")
    def mutate_a(shared_list):
        return {"result_a": len(shared_list), "a_list": [*shared_list, "a"]}

    @step("Mutate shared key B")
    def mutate_b(shared_list):
        return {"result_b": len(shared_list), "b_list": [*shared_list, "b"]}

    wf = workflow()(lambda: init >> parallel("mutate a and b", mutate_a, mutate_b) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"shared_list": [1, 2, 3]})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    # Initial state preserved, branch results not merged
    assert state["shared_list"] == [1, 2, 3]
    assert "result_a" not in state
    assert "result_b" not in state


# --- Test: Error handling ---


def test_single_branch_failure_fails_group():
    """If one branch fails, the parallel group fails."""
    wf = workflow()(lambda: init >> parallel("branch a and b", branch_a_step1, failing_branch_step) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)


def test_retryable_branch_returns_waiting():
    """If one branch is retryable (Waiting), the parallel group returns Waiting."""
    wf = workflow()(lambda: init >> parallel("branch a and b", branch_a_step1, retryable_branch_step) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_waiting(result)


def test_failure_takes_precedence_over_waiting():
    """Failed status takes precedence over Waiting."""
    wf = workflow()(lambda: init >> parallel("name", retryable_branch_step, failing_branch_step) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)


def test_steps_after_failed_parallel_not_executed():
    """Steps after a failed parallel block should not execute."""
    side_effects = []

    @step("Should not run")
    def should_not_run():
        side_effects.append("ran")
        return {}

    wf = workflow()(lambda: init >> parallel("name", failing_branch_step, branch_a_step1) >> should_not_run >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)
    assert side_effects == [], "Step after failed parallel should not execute"


# --- Test: Validation ---


def test_requires_at_least_two_branches():
    """parallel() with fewer than 2 branches raises ValueError."""
    with pytest.raises(ValueError, match="at least 2 branches"):
        parallel("Single branch", begin >> branch_a_step1)


def test_rejects_inputsteps_in_branches_via_parallel():
    """parallel() branches must not contain inputsteps."""

    @inputstep("User Input", assignee=Assignee.SYSTEM)  # type: ignore[untyped-decorator]
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


# --- Test: Conditional in parallel ---


def test_conditional_step_in_branch():
    """Conditional steps inside branches work correctly."""
    skip_b = conditional(lambda s: False)

    wf = workflow()(lambda: init >> parallel("name", branch_a_step1, skip_b(branch_b_step1)) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state


# --- Test: parallel steps the tree walk cannot see (safety net) ---
#
# _validate_unique_parallel_group_names only sees the steps the walk reaches. A parallel step hidden by a wrapper
# is not checked, and a worker cannot look it up by name. The safety net in _exec_parallel_branches fails loudly
# when such a step runs, instead of letting a worker rebuild the wrong branch.


def test_parallel_inside_conditional_is_visible_and_duplicates_are_detected():
    """conditional() copies the wrapped step's attributes, so the walk sees the parallel step inside it."""
    par = parallel("Conditional group", begin >> branch_a_step1, begin >> branch_b_step1)
    gated = conditional(lambda _state: True)(par)

    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Conditional group'\]"):

        @workflow()
        def duplicate_conditional_wf():
            return (
                init >> gated >> parallel("Conditional group", begin >> branch_a_step1, begin >> branch_b_step1) >> done
            )


@pytest.mark.parametrize(
    "predicate", [pytest.param(True, id="predicate-true"), pytest.param(False, id="predicate-false")]
)
def test_parallel_inside_conditional_runs_on_threadpool(predicate):
    """A parallel step inside conditional() runs (or is skipped) without tripping the safety net."""
    par = parallel("Conditional run group", begin >> branch_a_step1, begin >> branch_b_step1)
    gated = conditional(lambda _state: predicate)(par)

    wf = workflow()(lambda: init >> gated >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "b1" not in state


@pytest.mark.xfail(
    reason="step_group keeps its sub-steps in a closure, so the walk cannot see a parallel step inside it. "
    "Phase 4 adds Step.sub_steps.",
    strict=True,
)
def test_parallel_inside_step_group_is_visible():
    """A parallel step inside step_group must be visible to the walk once phase 4 adds Step.sub_steps."""
    group = step_group("Wrapper", begin >> parallel("Grouped", begin >> branch_a_step1, begin >> branch_b_step1))

    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Grouped'\]"):

        @workflow()
        def duplicate_step_group_wf():
            return init >> group >> parallel("Grouped", begin >> branch_a_step1, begin >> branch_b_step1) >> done


@pytest.mark.xfail(
    reason="step_group keeps its sub-steps in a closure, so the walk cannot see a parallel step inside it. "
    "Phase 4 adds Step.sub_steps.",
    strict=True,
)
def test_parallel_inside_step_group_runs():
    """Running a parallel step inside step_group is supported once phase 4 adds Step.sub_steps."""
    group = step_group("Wrapper", begin >> parallel("Grouped run", begin >> branch_a_step1, begin >> branch_b_step1))

    wf = workflow()(lambda: init >> group >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)


def test_parallel_inside_step_group_fails_the_safety_net():
    """Until phase 4, a parallel step inside step_group fails loudly instead of running unchecked."""
    group = step_group("Wrapper", begin >> parallel("Unreachable", begin >> branch_a_step1, begin >> branch_b_step1))

    wf = workflow()(lambda: init >> group >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)
    assert "not visible in the workflow's step tree" in str(result.unwrap())


@pytest.mark.xfail(
    reason="callback_step is built on step_group, so the walk cannot see a parallel step inside it. "
    "Phase 4 adds Step.sub_steps.",
    strict=True,
)
def test_parallel_inside_callback_step_is_visible():
    """A parallel step inside callback_step must be visible to the walk once phase 4 adds Step.sub_steps."""

    @step("CB Validate")
    def cb_validate():
        return {}

    cb = callback_step(
        "Callback wrapper",
        action_step=parallel("Called back", begin >> branch_a_step1, begin >> branch_b_step1),
        validate_step=cb_validate,
    )

    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Called back'\]"):

        @workflow()
        def duplicate_callback_wf():
            return init >> cb >> parallel("Called back", begin >> branch_a_step1, begin >> branch_b_step1) >> done


def test_parallel_step_with_a_reused_name_fails_the_safety_net():
    """A visible group name must belong to a step carrying this step's own branches."""
    first = parallel("Reused name", begin >> branch_a_step1, begin >> branch_b_step1)
    second = parallel("Reused name", begin >> branch_a_step1, begin >> branch_b_step1)

    @workflow()
    def reused_name_wf():
        return init >> first >> done

    # `second` was never added to this workflow, so the step found under its name has other branches.
    with pytest.raises(ValueError, match="reused by a parallel step with different branches"):
        _assert_parallel_step_is_visible(reused_name_wf.steps, "Reused name", list(_child_step_lists(second)))


def test_parallel_step_missing_from_the_step_list_fails_the_safety_net():
    """A parallel step the walk cannot reach at all is rejected instead of running unchecked."""
    par = parallel("Hidden group", begin >> branch_a_step1, begin >> branch_b_step1)

    @workflow()
    def without_parallel_wf():
        return init >> branch_a_step1 >> done

    with pytest.raises(ValueError, match="not visible in the workflow's step tree"):
        _assert_parallel_step_is_visible(without_parallel_wf.steps, "Hidden group", list(_child_step_lists(par)))


# --- Test: Composition ---


def test_parallel_after_step_group():
    """Parallel block works after a step_group."""
    group = step_group("Group", begin >> branch_a_step1)

    @step("Independent C")
    def step_c():
        return {"c": True}

    wf = workflow()(lambda: init >> group >> parallel("name", branch_b_step1, step_c) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    # step_group result IS in state (it's not a parallel branch)
    assert state["a1"] == "done"
    # parallel branch results are NOT in state
    assert "b1" not in state
    assert "c" not in state


def test_multiple_parallel_blocks_in_sequence():
    """Multiple parallel blocks can appear in the same workflow."""

    @step("Step D")
    def step_d():
        return {"d": True}

    @step("Step E")
    def step_e():
        return {"e": True}

    wf = workflow()(
        lambda: (
            init
            >> parallel("first block", branch_a_step1, branch_b_step1)
            >> parallel("second block", step_d, step_e)
            >> done
        )
    )

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "b1" not in state
    assert "d" not in state
    assert "e" not in state


# --- Test: Branch input state ---


def test_branches_receive_state_from_previous_step():
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

    wf = workflow()(lambda: init >> setup >> parallel("name", use_x, use_y) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    # Pre-parallel state preserved
    assert state["x"] == 42
    assert state["y"] == "hello"
    # Branch results NOT merged back
    assert "x_doubled" not in state
    assert "y_upper" not in state


# --- Test: Step logging ---


def test_named_parallel_group_appears_in_log():
    """A named parallel group appears with its name in the step log."""
    wf = workflow()(lambda: init >> {"My parallel block": [begin >> branch_a_step1, begin >> branch_b_step1]} >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    step_names = [entry[0] for entry in log]
    assert "My parallel block" in step_names
    assert "Done" in step_names


# --- Test: Thread execution ---


def test_branch_exception_does_not_crash_other_branches():
    """One branch raising does not prevent other branches from completing."""
    side_effects: list[str] = []

    @step("Good branch")
    def good_branch():
        time.sleep(0.05)
        side_effects.append("good_completed")
        return {"good": True}

    @step("Bad branch")
    def bad_branch():
        raise RuntimeError("boom")

    wf = workflow()(lambda: init >> parallel("name", good_branch, bad_branch) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)
    assert "good_completed" in side_effects, "Good branch should have completed despite other branch failing"


def test_each_branch_has_own_db_session():
    """Each branch thread should get its own database session via database_scope."""
    session_ids: list[int] = []
    lock = threading.Lock()

    @step("Record session A")
    def record_session_a():
        with lock:
            session_ids.append(id(db.session))
        return {"session_a": True}

    @step("Record session B")
    def record_session_b():
        with lock:
            session_ids.append(id(db.session))
        return {"session_b": True}

    wf = workflow()(lambda: init >> parallel("name", record_session_a, record_session_b) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    assert len(session_ids) == 2
    assert session_ids[0] != session_ids[1], "Each branch should have a distinct database session"


def test_deepcopy_isolation_with_threads():
    """Branches receive deep-copied state; shared mutable objects are independent copies."""
    observed_lengths: list[int] = []
    lock = threading.Lock()

    @step("Process list A")
    def process_list_a(items):
        with lock:
            observed_lengths.append(len(items))
        return {"a_snapshot": list(items), "a_len": len(items)}

    @step("Process list B")
    def process_list_b(items):
        with lock:
            observed_lengths.append(len(items))
        return {"b_snapshot": list(items), "b_len": len(items)}

    wf = workflow()(lambda: init >> parallel("name", process_list_a, process_list_b) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"items": [1, 2, 3]})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert all(length == 3 for length in observed_lengths)
    # Initial state preserved, branch results not merged
    assert state["items"] == [1, 2, 3]
    assert "a_len" not in state
    assert "b_len" not in state


# --- Test: map_parallel ---


def test_map_parallel_dict_items_seed_branch_state():
    """Dict items are merged into each branch's initial state; results stay in DB."""

    @step("Use seeded keys")
    def use_seeded(port_id, vlan):
        return {f"result_{port_id}": vlan * 2}

    wf = workflow()(lambda: init >> map_parallel("Provision ports", "ports", use_seeded) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(
            wf_table, {"ports": [{"port_id": "p1", "vlan": 100}, {"port_id": "p2", "vlan": 200}]}
        )
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    # Branch results NOT merged; initial state preserved
    assert "ports" in state
    assert "result_p1" not in state
    assert "result_p2" not in state


def test_map_parallel_scalar_items_injected_as_item_and_index():
    """Scalar items are injected as {"item": value, "item_index": idx}; results stay in DB."""

    @step("Use scalar item")
    def use_scalar(item, item_index):
        return {f"out_{item_index}": item * 10}

    wf = workflow()(lambda: init >> map_parallel("Process scalars", "values", use_scalar) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"values": [3, 7, 11]})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    # Branch results NOT merged; initial state preserved
    assert "values" in state
    assert "out_0" not in state
    assert "out_1" not in state
    assert "out_2" not in state


def test_map_parallel_initial_state_accessible_in_branches():
    """Branches can read both the item seed and the full upstream state."""

    @step("Combine upstream and seed")
    def combine(prefix, port_id):
        return {f"{prefix}_{port_id}": "provisioned"}

    wf = workflow()(lambda: init >> map_parallel("Ports", "ports", combine) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"prefix": "env", "ports": [{"port_id": "A"}, {"port_id": "B"}]})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    # Initial state preserved, branch results not merged
    assert "prefix" in state
    assert "env_A" not in state
    assert "env_B" not in state


def test_map_parallel_empty_list_returns_success_unchanged():
    """An empty items list returns Success with the original state, no threads."""

    @step("Should not run")
    def should_not_run():
        return {"ran": True}

    wf = workflow()(lambda: init >> map_parallel("Nothing", "items", should_not_run) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"items": []})
        result = runwf(pstat, store(log))

    assert_complete(result)
    assert "ran" not in result.unwrap()


def test_map_parallel_missing_key_raises_at_runtime():
    """Accessing a missing items_key raises ValueError during step execution."""

    @step("Noop")
    def noop():
        return {}

    wf = workflow()(lambda: init >> map_parallel("Oops", "nonexistent", noop) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)


def test_map_parallel_branch_failure_fails_group():
    """If one item's branch fails, the whole map_parallel group fails."""

    @step("Sometimes fails")
    def sometimes_fails(port_id):
        if port_id == "bad":
            raise ValueError("bad port")
        return {f"ok_{port_id}": True}

    wf = workflow()(lambda: init >> map_parallel("Ports", "ports", sometimes_fails) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"ports": [{"port_id": "good"}, {"port_id": "bad"}]})
        result = runwf(pstat, store(log))

    assert_failed(result)


def test_map_parallel_appears_as_single_step_in_log():
    """map_parallel appears as a single named step in the process log."""

    @step("Process item")
    def process_item(port_id):
        return {f"r_{port_id}": True}

    wf = workflow()(lambda: init >> map_parallel("Provision ports", "ports", process_item) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"ports": [{"port_id": "p1"}, {"port_id": "p2"}]})
        result = runwf(pstat, store(log))

    assert_complete(result)
    step_names = [entry[0] for entry in log]
    assert "Provision ports" in step_names
    assert "Done" in step_names


# --- Test: __replace_last_state on the parallel step must not corrupt branch rows ---


@pytest.mark.parametrize(
    "branch_count",
    [
        pytest.param(2, id="two-branches"),
        pytest.param(3, id="three-branches"),
        pytest.param(5, id="five-branches"),
    ],
)
def test_parallel_join_preserves_branch_row_state(branch_count):
    """Branch step rows retain their full state after the parallel join.

    Regression test. Before the fix, the parallel step returned ``__replace_last_state=True``
    and ``_get_current_step_to_update`` picked the most-recently-completed step row by
    ``completed_at DESC``. In a parallel context, that row is the last-finishing branch,
    so the parent workflow's state would overwrite that branch's state in the DB.

    Fix: ``_get_current_step_to_update`` excludes rows that are children of a fork step
    (via ``process_step_relations``) from the ``last_db_step`` query, and preserves the
    fork step's original timestamps when updating it.
    """

    @step("Capture item")
    def capture_item(item, item_index):
        return {f"branch_{item_index}_done": True, f"branch_{item_index}_label": item}

    @step("Seed items")
    def seed_items():
        return {"items": [f"item-{i}" for i in range(branch_count)]}

    wf = workflow()(lambda: init >> seed_items >> map_parallel("Fan out", "items", capture_item) >> done)

    with register_test_workflow(wf) as wf_table:
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, partial(safe_logstep))
        assert_complete(result)

        # Queries must happen before the context manager exits — it cascade-deletes
        # the workflow row, taking the process and all its steps with it.
        db.session.commit()
        fan_out_rows = db.session.scalars(
            select(ProcessStepTable)
            .options(
                selectinload(ProcessStepTable.child_step_relations).selectinload(ProcessStepRelationTable.child_step)
            )
            .where(
                ProcessStepTable.process_id == pstat.process_id,
                ProcessStepTable.name == "Fan out",
            )
        ).all()
        assert len(fan_out_rows) == 1, f"expected 1 'Fan out' row, got {len(fan_out_rows)}"
        fork_step = fan_out_rows[0]
        children = list(fork_step.child_steps)

        assert len(children) == branch_count, f"expected {branch_count} branch rows, got {len(children)}"

        def has_branch_marker(child):
            return any(child.state.get(f"branch_{i}_done") is True for i in range(branch_count))

        missing = [c for c in children if not has_branch_marker(c)]
        assert not missing, f"branch rows missing step return state: {[(c.name, c.state) for c in missing]}"

        # Fork step's completed_at must not have been bumped past the branches; it was set
        # by _create_fork_step before branches ran and must stay there so the UI displays
        # the fork step before its children.
        assert all(fork_step.completed_at <= child.completed_at for child in children), (
            "fork step completed_at was bumped after branches — ordering broken"
        )


# --- Test: the transaction around the join in run_worker_branch ---
#
# The worker path runs each branch through ``run_worker_branch``. The increment of ``branches_completed`` and, for the
# last finisher, the fork update form one transaction that is committed before the RESUME executor is called. The
# resume dispatch is stubbed, so these tests cover only the DB work of the worker.


def _make_fork_step(process_id, name: str, branch_count: int, state: dict) -> ProcessStepTable:
    """Insert a fork step that is waiting for ``branch_count`` branches, like ``_create_fork_step`` does.

    Branches are not dispatched: each test runs a branch with ``run_worker_branch`` itself.
    """
    fork_step = ProcessStepTable(
        process_id=process_id,
        name=name,
        status=ProcessStatus.WAITING,
        state=state,
        created_by=SYSTEM_USER,
        branch_count=branch_count,
        branch_kind=BranchKind.PARALLEL,
        branches_completed=0,
    )
    db.session.add(fork_step)
    db.session.commit()
    return fork_step


def _make_branch_result(fork_step: ProcessStepTable, branch_index: int, status: str) -> None:
    """Link a finished branch step to the fork, as the branch's DB step logger would."""
    child_step = ProcessStepTable(
        process_id=fork_step.process_id,
        name=f"[Branch {branch_index}] {fork_step.name}",
        status=status,
        state={"branch": branch_index},
        created_by=SYSTEM_USER,
    )
    db.session.add(child_step)
    db.session.flush()
    db.session.add(
        ProcessStepRelationTable(
            parent_step_id=fork_step.step_id,
            child_step_id=child_step.step_id,
            order_id=0,
            branch_index=branch_index,
        )
    )
    db.session.commit()


class _ResumeCalls:
    """Stub for ``get_execution_context`` that records resume calls instead of handing over to an executor."""

    def __init__(self) -> None:
        self.process_ids: list = []

    def resume(self, process, user: str = SYSTEM_USER) -> None:  # noqa: ARG002
        self.process_ids.append(process.process_id)

    def __getitem__(self, executor_function: ExecutorFunction) -> Callable:
        if executor_function is not ExecutorFunction.RESUME:
            raise AssertionError(f"run_worker_branch must only call the RESUME executor, not {executor_function}")
        return self.resume


@contextmanager
def _worker_branch_environment(workflow_key: str, join_group: str = "Worker join group") -> Iterator[_ResumeCalls]:
    """Register a workflow with a two-branch parallel step and stub the resume dispatch of ``run_worker_branch``."""
    resume_calls = _ResumeCalls()

    par = parallel(join_group, begin >> branch_a_step1, begin >> branch_b_step1)

    @workflow()
    def worker_join_wf():
        return init >> par >> done

    with (
        WorkflowInstanceForTests(worker_join_wf, workflow_key),
        patch("orchestrator.core.services.processes.get_execution_context", return_value=resume_calls),
    ):
        yield resume_calls


def test_run_worker_branch_non_last_branch_increments_without_resuming():
    """A branch that is not the last one increments the counter, leaves the fork unresolved and doesn't resume."""
    with _worker_branch_environment("worker_join_non_last_wf") as resume_calls:
        pstat = create_process("worker_join_non_last_wf", [{}])
        initial_state = pstat.state.unwrap()
        fork_step = _make_fork_step(pstat.process_id, "Worker join group", branch_count=2, state=initial_state)
        _make_branch_result(fork_step, branch_index=0, status=StepStatus.SUCCESS)

        run_worker_branch(
            process_id=pstat.process_id,
            branch_index=0,
            fork_step_id=fork_step.step_id,
            initial_state=initial_state,
            user=SYSTEM_USER,
        )

        db.session.expire_all()
        fork_step = db.session.get(ProcessStepTable, fork_step.step_id)
        assert fork_step.branches_completed == 1
        assert fork_step.status == ProcessStatus.WAITING
        # The fork keeps the pre-parallel state until the last branch resolves it.
        assert fork_step.state == {**initial_state, "process_id": str(pstat.process_id)}
        assert resume_calls.process_ids == []


@pytest.mark.parametrize(
    "branch_status, expected_status",
    [
        pytest.param(StepStatus.SUCCESS, StepStatus.SUCCESS, id="all-succeeded"),
        pytest.param(StepStatus.FAILED, StepStatus.FAILED, id="one-failed"),
        pytest.param(StepStatus.WAITING, StepStatus.WAITING, id="one-waiting"),
        pytest.param(StepStatus.AWAITING_CALLBACK, StepStatus.AWAITING_CALLBACK, id="one-awaiting-callback"),
        pytest.param(StepStatus.SUSPEND, StepStatus.SUSPEND, id="one-suspend"),
    ],
)
def test_run_worker_branch_last_finisher_resolves_fork_and_resumes_once(branch_status, expected_status):
    """The last finisher sets the fork's status from the worst branch and resumes the process exactly once."""
    with _worker_branch_environment("worker_join_last_wf") as resume_calls:
        pstat = create_process("worker_join_last_wf", [{}])
        initial_state = pstat.state.unwrap()
        fork_step = _make_fork_step(pstat.process_id, "Worker join group", branch_count=2, state=initial_state)

        # Branch 0 ran earlier and left its result in the DB.
        _make_branch_result(fork_step, branch_index=0, status=branch_status)
        db.session.execute(
            update(ProcessStepTable).where(ProcessStepTable.step_id == fork_step.step_id).values(branches_completed=1)
        )
        db.session.commit()

        # Branch 1 is the last finisher and succeeds.
        run_worker_branch(
            process_id=pstat.process_id,
            branch_index=1,
            fork_step_id=fork_step.step_id,
            initial_state=initial_state,
            user=SYSTEM_USER,
        )

        db.session.expire_all()
        fork_step = db.session.get(ProcessStepTable, fork_step.step_id)
        assert fork_step.branches_completed == 2
        assert fork_step.status == expected_status
        assert resume_calls.process_ids == [pstat.process_id]


def test_run_worker_branch_makes_the_process_available_to_nested_parallel_steps():
    """While a branch runs, ``process_stat_var`` holds this process, its user and its workflow.

    A parallel step nested in a branch has no other way to know its process: ``_exec_parallel_branches`` reads
    ``process_id``, ``current_user`` and ``workflow.name`` from the context variable to create the nested fork and
    dispatch its branches, and looks the workflow up by name on the worker. Resolving one branch therefore has to
    install it before the branch executes.
    """
    seen: list[ProcessStat | None] = []

    with _worker_branch_environment("worker_nested_context_wf"):
        pstat = create_process("worker_nested_context_wf", [{}])
        initial_state = pstat.state.unwrap()
        fork_step = _make_fork_step(pstat.process_id, "Worker join group", branch_count=1, state=initial_state)

        # Stand in for the branch's steps and record the process context the worker set up for them.
        with patch.object(
            parallel_service, "_exec_steps", side_effect=lambda *_args: seen.append(process_stat_var.get(None))
        ):
            run_worker_branch(
                process_id=pstat.process_id,
                branch_index=0,
                fork_step_id=fork_step.step_id,
                initial_state=initial_state,
                user=TEST_USER,
            )

    assert len(seen) == 1, "the branch must have been executed once"
    branch_stat = seen[0]
    assert branch_stat is not None, "a nested parallel step in the branch would not find its process"
    assert branch_stat.process_id == pstat.process_id
    assert branch_stat.current_user == TEST_USER
    assert branch_stat.workflow.name == "worker_nested_context_wf"


def test_run_worker_branch_failing_resume_leaves_fork_resolved():
    """A failing RESUME must not undo the join: the fork row is committed before the hand-off.

    If the fork update were rolled back with a failing resume, the fork would stay ``waiting``. The parallel step then
    looks undone, and a manual resume would run every branch again.
    """
    with _worker_branch_environment("worker_join_failing_resume_wf") as resume_calls:
        pstat = create_process("worker_join_failing_resume_wf", [{}])
        initial_state = pstat.state.unwrap()
        fork_step = _make_fork_step(pstat.process_id, "Worker join group", branch_count=1, state=initial_state)

        with (
            patch.object(resume_calls, "resume", side_effect=AssertionError("incorrect status to resume")),
            pytest.raises(AssertionError, match="incorrect status to resume"),
        ):
            run_worker_branch(
                process_id=pstat.process_id,
                branch_index=0,
                fork_step_id=fork_step.step_id,
                initial_state=initial_state,
                user=SYSTEM_USER,
            )

        db.session.expire_all()
        fork_step = db.session.get(ProcessStepTable, fork_step.step_id)
        assert fork_step.branches_completed == 1
        assert fork_step.status == StepStatus.SUCCESS


def test_resolve_fork_step_missing_fork_step_raises_and_logs_ids():
    """A missing fork step must not be skipped: the process would resume with the parallel step unresolved.

    In practice the counter update already fails on a missing fork row, so this is exercised on the fork lookup
    directly.
    """
    process_id = uuid4()
    fork_step_id = uuid4()
    logger_mock = MagicMock()

    with (
        patch.object(parallel_service, "logger", logger_mock),
        pytest.raises(ValueError, match=f"Fork step {fork_step_id} not found"),
    ):
        _resolve_fork_step(process_id=process_id, fork_step_id=fork_step_id, initial_state={})

    # The ids make the stuck process findable.
    logger_mock.error.assert_called_once_with(
        "Fork step not found while resolving parallel branches",
        process_id=str(process_id),
        fork_step_id=str(fork_step_id),
    )


# --- Test: current behaviour when a worker crashes before the join ---
#
# Out of scope for the transaction around the join (see docs/designs/parallel-steps-todos.md, phase 2); recovery is
# tracked separately. This test documents what happens today, so the follow-up has a starting point.


def test_worker_crash_before_the_join_leaves_the_process_stuck_in_waiting():
    """A worker that commits its branch and then dies before the join leaves the process stuck in Waiting.

    The workflow runs on the worker path, so it suspends on the fork row and dispatches both branches. The dispatch is
    stubbed, so no branch runs. Then one branch commits its result and its increment, and the worker dies before the
    join; the other branch never reports. Nobody resolves the fork row: it stays ``waiting`` with one branch completed,
    the process stays Waiting, and a resume runs the whole parallel step again instead of just the missing branch.
    """
    task = MagicMock()

    @workflow()
    def worker_crash_wf():
        return init >> parallel("Worker crash group", begin >> branch_a_step1, begin >> branch_b_step1) >> done

    with WorkflowInstanceForTests(worker_crash_wf, "worker_crash_wf"):
        with (
            patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER),
            # Dispatching the branch tasks returns without running them, as the workers would run them out of band.
            patch("orchestrator.core.services.tasks.get_celery_task", return_value=task),
        ):
            pstat = create_process("worker_crash_wf", [{}])
            result = runwf(pstat, partial(safe_logstep))

        assert result.iswaiting(), f"Expected Waiting (WORKER mode), but was: {result}"
        assert len(task.delay.call_args_list) == 2, "both branches must be dispatched"

        db.session.expire_all()
        process = db.session.get(ProcessTable, pstat.process_id)
        assert process.last_status == ProcessStatus.WAITING
        fork_step = db.session.get(ProcessStepTable, result.unwrap()["__fork_step_id"])
        assert fork_step.status == StepStatus.WAITING
        assert fork_step.branches_completed == 0

        # One branch commits its result and its increment; its worker dies before the join.
        _make_branch_result(fork_step, branch_index=0, status=StepStatus.SUCCESS)
        db.session.execute(
            update(ProcessStepTable).where(ProcessStepTable.step_id == fork_step.step_id).values(branches_completed=1)
        )
        db.session.commit()

        # Nothing resolves the fork row, so the process stays Waiting on it.
        db.session.expire_all()
        assert db.session.get(ProcessTable, pstat.process_id).last_status == ProcessStatus.WAITING
        fork_step = db.session.get(ProcessStepTable, fork_step.step_id)
        assert fork_step.status == StepStatus.WAITING
        assert fork_step.branches_completed == 1

        # A resume offers the parallel step again. The fork row is not failed, so its finished branch is not inherited
        # and every branch runs again, including the branch that already finished.
        loaded_pstat = load_process(db.session.get(ProcessTable, pstat.process_id))
        assert [s.name for s in loaded_pstat.log] == ["Worker crash group", "Done"]

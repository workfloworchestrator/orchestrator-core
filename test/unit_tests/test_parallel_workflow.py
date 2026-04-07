"""Tests for parallel step execution in the workflow engine.

Branch results are NOT merged into the main workflow state. After a parallel
block, the next step receives the pre-parallel (initial) state. Branch data
is persisted in the DB and accessible via ProcessStepRelationTable / child_steps.
"""

import threading
import time
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import close_all_sessions, sessionmaker

from orchestrator.config.assignee import Assignee
from orchestrator.db import ProcessTable, db
from orchestrator.db.database import SESSION_ARGUMENTS, BaseModel, SearchQuery
from orchestrator.services.processes import SYSTEM_USER
from orchestrator.workflow import (
    ParallelStepList,
    ProcessStat,
    ProcessStatus,
    Success,
    begin,
    conditional,
    done,
    foreach_parallel,
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
    WorkflowInstanceForTests,
    assert_complete,
    assert_failed,
    assert_waiting,
)


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
    from orchestrator.workflows import get_workflow

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


# --- Test: | operator and ParallelStepList ---


def test_pipe_creates_parallel_step_list():
    """StepList | StepList creates a ParallelStepList with 2 branches."""
    branch_a = begin >> branch_a_step1
    branch_b = begin >> branch_b_step1
    par = branch_a | branch_b

    assert isinstance(par, ParallelStepList)
    assert len(par.branches) == 2


def test_pipe_chaining_creates_multiple_branches():
    """A | b | c creates a ParallelStepList with 3 branches."""
    branch_a = begin >> branch_a_step1
    branch_b = begin >> branch_b_step1

    @step("Branch C")
    def branch_c():
        return {"c1": "done"}

    par = branch_a | branch_b | (begin >> branch_c)
    assert isinstance(par, ParallelStepList)
    assert len(par.branches) == 3


def test_pipe_operator_precedence_with_rshift():
    """>> binds tighter than |, so begin >> step_a | begin >> step_b works."""
    par = begin >> branch_a_step1 | begin >> branch_b_step1

    assert isinstance(par, ParallelStepList)
    assert len(par.branches) == 2


@pytest.mark.parametrize(
    "make_wf",
    [
        pytest.param(
            lambda: workflow()(lambda: init >> ((begin >> branch_a_step1) | (begin >> branch_b_step1)) >> done),
            id="unnamed-pipe-operator",
        ),
        pytest.param(
            lambda: workflow()(
                lambda: init >> {"Block": (begin >> branch_a_step1) | (begin >> branch_b_step1)} >> done
            ),
            id="named-dict-syntax",
        ),
    ],
)
def test_two_branch_parallel_passes_initial_state(make_wf):
    """Two-branch parallel passes initial state through; branch state is NOT merged."""
    wf = make_wf()
    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "b1" not in state


# --- Test: Dict naming syntax ---


def test_dict_with_parallel_step_list():
    """{"name": branch_a | branch_b} creates a named parallel step."""
    wf = workflow()(lambda: init >> {"Provision ports": (begin >> branch_a_step1) | (begin >> branch_b_step1)} >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "b1" not in state

    step_names = [entry[0] for entry in log]
    assert "Provision ports" in step_names


def test_dict_with_list_of_steplists():
    """{"name": [branch_a, branch_b]} also works as alternative."""
    wf = workflow()(
        lambda: init
        >> {
            "Provision ports": [
                begin >> branch_a_step1,
                begin >> branch_b_step1,
            ]
        }
        >> done
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
            "a": (begin >> branch_a_step1) | (begin >> branch_b_step1),
            "b": (begin >> branch_a_step1) | (begin >> branch_b_step1),
        }


def test_dict_with_non_string_key_raises():
    """Dict with non-string key raises ValueError."""
    with pytest.raises(ValueError):
        begin >> {42: (begin >> branch_a_step1) | (begin >> branch_b_step1)}


# --- Test: Basic parallel execution ---


def test_two_branches_pass_initial_state():
    """Two branches execute; post-parallel state is the pre-parallel state."""
    wf = workflow()(
        lambda: init >> seq_before >> {"Parallel block": (begin >> branch_a_step1) | (begin >> branch_b_step1)} >> done
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
        lambda: init
        >> ((begin >> branch_a_step1 >> branch_a_step1_cont) | (begin >> branch_b_step1 >> branch_b_step1_cont))
        >> done
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
        lambda: init >> ((begin >> branch_a_step1) | (begin >> branch_b_step1) | (begin >> branch_c)) >> done
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

    wf = workflow()(lambda: init >> ((begin >> mutate_a) | (begin >> mutate_b)) >> done)

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
    wf = workflow()(lambda: init >> ((begin >> branch_a_step1) | (begin >> failing_branch_step)) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)


def test_retryable_branch_returns_waiting():
    """If one branch is retryable (Waiting), the parallel group returns Waiting."""
    wf = workflow()(lambda: init >> ((begin >> branch_a_step1) | (begin >> retryable_branch_step)) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_waiting(result)


def test_failure_takes_precedence_over_waiting():
    """Failed status takes precedence over Waiting."""
    wf = workflow()(lambda: init >> ((begin >> retryable_branch_step) | (begin >> failing_branch_step)) >> done)

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

    wf = workflow()(
        lambda: init >> ((begin >> failing_branch_step) | (begin >> branch_a_step1)) >> should_not_run >> done
    )

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


def test_parallel_step_list_requires_two_branches():
    """ParallelStepList with fewer than 2 branches raises ValueError."""
    with pytest.raises(ValueError, match="at least 2 branches"):
        ParallelStepList([begin >> branch_a_step1])


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


def test_rejects_inputsteps_in_branches_via_pipe():
    """| operator with inputsteps raises ValueError when composed with >>."""

    @inputstep("User Input", assignee=Assignee.SYSTEM)  # type: ignore[untyped-decorator]
    def user_input() -> type[FormPage]:
        class Form(FormPage):
            name: str

        return Form

    with pytest.raises(ValueError, match="must not contain inputsteps"):
        begin >> ((begin >> branch_a_step1) | (begin >> user_input))


# --- Test: Conditional in parallel ---


def test_conditional_step_in_branch():
    """Conditional steps inside branches work correctly."""
    skip_b = conditional(lambda s: False)

    wf = workflow()(lambda: init >> ((begin >> branch_a_step1) | skip_b(branch_b_step1)) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state


# --- Test: Composition ---


def test_parallel_after_step_group():
    """Parallel block works after a step_group."""
    group = step_group("Group", begin >> branch_a_step1)

    @step("Independent C")
    def step_c():
        return {"c": True}

    wf = workflow()(lambda: init >> group >> ((begin >> branch_b_step1) | (begin >> step_c)) >> done)

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
        lambda: init
        >> ((begin >> branch_a_step1) | (begin >> branch_b_step1))
        >> ((begin >> step_d) | (begin >> step_e))
        >> done
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


def test_parallel_function_still_works():
    """The explicit parallel() function continues to work for advanced use cases."""
    par = parallel("Explicit parallel", begin >> branch_a_step1, begin >> branch_b_step1)
    wf = workflow()(lambda: init >> par >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    state = result.unwrap()
    assert "a1" not in state
    assert "b1" not in state


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

    wf = workflow()(lambda: init >> setup >> ((begin >> use_x) | (begin >> use_y)) >> done)

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
    wf = workflow()(
        lambda: init >> {"My parallel block": (begin >> branch_a_step1) | (begin >> branch_b_step1)} >> done
    )

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    step_names = [entry[0] for entry in log]
    assert "My parallel block" in step_names
    assert "Done" in step_names


def test_unnamed_parallel_gets_auto_name_in_log():
    """An unnamed parallel group gets an auto-generated name in the step log."""
    wf = workflow()(lambda: init >> ((begin >> branch_a_step1) | (begin >> branch_b_step1)) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_complete(result)
    step_names = [entry[0] for entry in log]
    parallel_names = [n for n in step_names if "Parallel" in n or "Branch" in n]
    assert len(parallel_names) >= 1, f"Expected auto-named parallel step in log, got: {step_names}"


# --- Test: Thread execution ---


def test_branches_execute_concurrently():
    """Two branches each sleeping 0.1s should complete in ~0.1s, not ~0.2s."""

    @step("Slow A")
    def slow_a():
        time.sleep(0.1)
        return {"slow_a": "done"}

    @step("Slow B")
    def slow_b():
        time.sleep(0.1)
        return {"slow_b": "done"}

    wf = workflow()(lambda: init >> ((begin >> slow_a) | (begin >> slow_b)) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})

        start = time.monotonic()
        result = runwf(pstat, store(log))
        elapsed = time.monotonic() - start

    assert_complete(result)
    assert elapsed < 0.18, f"Expected concurrent execution (<0.18s), but took {elapsed:.3f}s"


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

    wf = workflow()(lambda: init >> ((begin >> good_branch) | (begin >> bad_branch)) >> done)

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

    wf = workflow()(lambda: init >> ((begin >> record_session_a) | (begin >> record_session_b)) >> done)

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

    wf = workflow()(lambda: init >> ((begin >> process_list_a) | (begin >> process_list_b)) >> done)

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


# --- Test: foreach_parallel ---


def test_foreach_dict_items_seed_branch_state():
    """Dict items are merged into each branch's initial state; results stay in DB."""

    @step("Use seeded keys")
    def use_seeded(port_id, vlan):
        return {f"result_{port_id}": vlan * 2}

    wf = workflow()(lambda: init >> foreach_parallel("Provision ports", "ports", begin >> use_seeded) >> done)

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


def test_foreach_scalar_items_injected_as_item_and_index():
    """Scalar items are injected as {"item": value, "item_index": idx}; results stay in DB."""

    @step("Use scalar item")
    def use_scalar(item, item_index):
        return {f"out_{item_index}": item * 10}

    wf = workflow()(lambda: init >> foreach_parallel("Process scalars", "values", begin >> use_scalar) >> done)

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


def test_foreach_initial_state_accessible_in_branches():
    """Branches can read both the item seed and the full upstream state."""

    @step("Combine upstream and seed")
    def combine(prefix, port_id):
        return {f"{prefix}_{port_id}": "provisioned"}

    wf = workflow()(lambda: init >> foreach_parallel("Ports", "ports", begin >> combine) >> done)

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


def test_foreach_empty_list_returns_success_unchanged():
    """An empty items list returns Success with the original state, no threads."""

    @step("Should not run")
    def should_not_run():
        return {"ran": True}

    wf = workflow()(lambda: init >> foreach_parallel("Nothing", "items", begin >> should_not_run) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"items": []})
        result = runwf(pstat, store(log))

    assert_complete(result)
    assert "ran" not in result.unwrap()


def test_foreach_missing_key_raises_at_runtime():
    """Accessing a missing items_key raises ValueError during step execution."""

    @step("Noop")
    def noop():
        return {}

    wf = workflow()(lambda: init >> foreach_parallel("Oops", "nonexistent", begin >> noop) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))

    assert_failed(result)


def test_foreach_branch_failure_fails_group():
    """If one item's branch fails, the whole foreach group fails."""

    @step("Sometimes fails")
    def sometimes_fails(port_id):
        if port_id == "bad":
            raise ValueError("bad port")
        return {f"ok_{port_id}": True}

    wf = workflow()(lambda: init >> foreach_parallel("Ports", "ports", begin >> sometimes_fails) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"ports": [{"port_id": "good"}, {"port_id": "bad"}]})
        result = runwf(pstat, store(log))

    assert_failed(result)


def test_foreach_executes_concurrently():
    """N items each sleeping 0.1s complete in ~0.1s, not N * 0.1s."""

    @step("Slow step")
    def slow_step(port_id):
        time.sleep(0.1)
        return {f"done_{port_id}": True}

    wf = workflow()(lambda: init >> foreach_parallel("Ports", "ports", begin >> slow_step) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"ports": [{"port_id": "p1"}, {"port_id": "p2"}, {"port_id": "p3"}]})

        start = time.monotonic()
        result = runwf(pstat, store(log))
        elapsed = time.monotonic() - start

    assert_complete(result)
    assert elapsed < 0.25, f"Expected concurrent execution, but took {elapsed:.3f}s"


def test_foreach_appears_as_single_step_in_log():
    """foreach_parallel appears as a single named step in the process log."""

    @step("Process item")
    def process_item(port_id):
        return {f"r_{port_id}": True}

    wf = workflow()(lambda: init >> foreach_parallel("Provision ports", "ports", begin >> process_item) >> done)

    with register_test_workflow(wf) as wf_table:
        log = []
        pstat = create_new_process_stat(wf_table, {"ports": [{"port_id": "p1"}, {"port_id": "p2"}]})
        result = runwf(pstat, store(log))

    assert_complete(result)
    step_names = [entry[0] for entry in log]
    assert "Provision ports" in step_names
    assert "Done" in step_names

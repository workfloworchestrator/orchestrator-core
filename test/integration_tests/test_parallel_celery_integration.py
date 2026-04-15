"""Integration tests for Celery-based parallel branch execution.

Tests exercise real DB persistence through the parallel execution path.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest

from orchestrator.db import ProcessStepTable, db
from orchestrator.services.parallel import (
    _atomic_increment_completed,
    _collect_branch_results,
    _resolve_branch_from_db,
)
from orchestrator.settings import ExecutorType, app_settings
from orchestrator.workflow import (
    begin,
    done,
    foreach_parallel,
    init,
    parallel,
    step,
    workflow,
)
from test.unit_tests.workflows import WorkflowInstanceForTests, assert_complete, run_workflow

# --- Step definitions ---


@step("Celery Branch A")
def cel_branch_a() -> dict:
    return {"cel_a": "done"}


@step("Celery Branch B")
def cel_branch_b() -> dict:
    return {"cel_b": "done"}


@step("Multi A1")
def multi_a1() -> dict:
    return {"a1": "first"}


@step("Multi A2")
def multi_a2(a1: str) -> dict:
    return {"a2": f"{a1}_second"}


@step("Multi B1")
def multi_b1() -> dict:
    return {"b1": "only"}


@step("Seq Step")
def seq_step() -> dict:
    return {"seq": "done"}


@step("Final Step")
def final_step() -> dict:
    return {"final": "done"}


@step("Process FE Item")
def process_fe_item(item: object, item_index: int) -> dict:
    return {f"result_{item_index}": f"processed_{item}"}


@step("Seed FE Items")
def seed_fe_items() -> dict:
    return {"items": ["alpha", "beta", "gamma"]}


# --- Query helpers ---


def _get_fork_step(process_id: object) -> ProcessStepTable:
    """Return the single fork step for a given process."""
    return (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .one()
    )


def _get_all_steps(process_id: object) -> list[ProcessStepTable]:
    """Return all process steps ordered by creation."""
    return (
        db.session.query(ProcessStepTable)
        .filter(ProcessStepTable.process_id == process_id)
        .order_by(ProcessStepTable.step_id)
        .all()
    )


# --- Tests ---


@pytest.mark.celery
def test_atomic_increment_completed_with_real_db() -> None:
    """Run a 2-branch parallel workflow, reset counter, then verify atomic increment."""

    @workflow()
    def cel_incr_wf():
        return init >> parallel("incr group", begin >> cel_branch_a, begin >> cel_branch_b) >> done

    with WorkflowInstanceForTests(cel_incr_wf, "cel_incr_wf"):
        result, pstat, _step_log = run_workflow("cel_incr_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)
        assert fork_step.parallel_completed_count == 2
        assert fork_step.parallel_total_branches == 2

        # Reset counter to test _atomic_increment_completed directly
        fork_step.parallel_completed_count = 0
        db.session.commit()

        first_completed, first_total = _atomic_increment_completed(fork_step.step_id)
        assert first_completed == 1
        assert first_total == 2

        second_completed, second_total = _atomic_increment_completed(fork_step.step_id)
        assert second_completed == 2
        assert second_total == 2


@pytest.mark.celery
def test_collect_branch_results_from_real_db() -> None:
    """Run a 2-branch parallel workflow and collect branch results from DB."""

    @workflow()
    def cel_collect_wf():
        return init >> parallel("collect group", begin >> cel_branch_a, begin >> cel_branch_b) >> done

    with WorkflowInstanceForTests(cel_collect_wf, "cel_collect_wf"):
        result, pstat, _step_log = run_workflow("cel_collect_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)
        branch_results = _collect_branch_results(fork_step.step_id)

        assert len(branch_results) == 2

        # Results are sorted by branch_index
        assert branch_results[0][0] == 0
        assert branch_results[1][0] == 1

        # Each branch should have "success" status
        assert branch_results[0][2] == "success"
        assert branch_results[1][2] == "success"

        # Collect all state keys across branches
        all_state_keys = {key for _idx, state, _status in branch_results for key in state}
        assert "cel_a" in all_state_keys
        assert "cel_b" in all_state_keys


@pytest.mark.celery
def test_collect_branch_results_multi_step_returns_last_step() -> None:
    """Branch with multiple steps returns accumulated state from the last step."""

    @workflow()
    def cel_multi_step_wf():
        return init >> parallel("multi step group", begin >> multi_a1 >> multi_a2, begin >> multi_b1) >> done

    with WorkflowInstanceForTests(cel_multi_step_wf, "cel_multi_step_wf"):
        result, pstat, _step_log = run_workflow("cel_multi_step_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)
        branch_results = _collect_branch_results(fork_step.step_id)

        assert len(branch_results) == 2

        # Branch 0 has 2 steps (multi_a1 >> multi_a2); the last step's state should have both keys
        branch_0_results = [r for r in branch_results if r[0] == 0]
        assert len(branch_0_results) == 1
        branch_0_state = branch_0_results[0][1]
        assert "a1" in branch_0_state
        assert "a2" in branch_0_state
        assert branch_0_state["a2"] == "first_second"

        # Branch 1 has 1 step
        branch_1_results = [r for r in branch_results if r[0] == 1]
        assert len(branch_1_results) == 1
        assert "b1" in branch_1_results[0][1]


@pytest.mark.celery
def test_resolve_branch_from_db_finds_correct_branch() -> None:
    """Resolve branch metadata from DB after running a parallel workflow."""

    @workflow()
    def cel_resolve_wf():
        return init >> parallel("resolve group", begin >> cel_branch_a, begin >> cel_branch_b) >> done

    with WorkflowInstanceForTests(cel_resolve_wf, "cel_resolve_wf"):
        result, pstat, _step_log = run_workflow("cel_resolve_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)

        group_name_0, branch_steps_0, process_0, wf_0 = _resolve_branch_from_db(fork_step.step_id, pstat.process_id, 0)
        assert group_name_0 == "resolve group"
        assert len(branch_steps_0) > 0
        assert process_0.process_id == pstat.process_id
        assert wf_0 is not None

        group_name_1, branch_steps_1, process_1, wf_1 = _resolve_branch_from_db(fork_step.step_id, pstat.process_id, 1)
        assert group_name_1 == "resolve group"
        assert len(branch_steps_1) > 0
        assert process_1.process_id == pstat.process_id
        assert wf_1 is not None


@pytest.mark.celery
def test_resolve_branch_from_db_invalid_fork_step_raises() -> None:
    """Non-existent fork step ID raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        _resolve_branch_from_db(uuid4(), uuid4(), 0)


@pytest.mark.celery
def test_foreach_parallel_branch_results_in_db() -> None:
    """foreach_parallel over 3 dict items creates 3 branches with correct per-item states."""

    @workflow()
    def cel_foreach_wf():
        return init >> seed_fe_items >> foreach_parallel("fe group", "items", begin >> process_fe_item) >> done

    with WorkflowInstanceForTests(cel_foreach_wf, "cel_foreach_wf"):
        result, pstat, _step_log = run_workflow("cel_foreach_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)
        branch_results = _collect_branch_results(fork_step.step_id)

        assert len(branch_results) == 3

        # Verify branch indices
        indices = {r[0] for r in branch_results}
        assert indices == {0, 1, 2}

        # Each branch should have processed its item
        all_state_keys = {key for _idx, state, _status in branch_results for key in state}
        assert "result_0" in all_state_keys
        assert "result_1" in all_state_keys
        assert "result_2" in all_state_keys


@pytest.mark.celery
def test_full_parallel_workflow_db_state_after_completion() -> None:
    """Complete workflow with sequential and parallel steps creates correct DB state.

    Note: in tests, only the fork step and branch steps are persisted to DB
    (regular steps use an in-memory step log). We verify the parallel-specific
    DB rows and the step_log for the full sequence.
    """

    @workflow()
    def cel_full_wf():
        return (
            init
            >> seq_step
            >> parallel("full group", begin >> cel_branch_a, begin >> cel_branch_b)
            >> final_step
            >> done
        )

    with WorkflowInstanceForTests(cel_full_wf, "cel_full_wf"):
        result, pstat, step_log = run_workflow("cel_full_wf", [{}])
        assert_complete(result)

        # Verify workflow sequence via step_log (in-memory).
        # Note: the parallel group step uses __replace_last_state which replaces
        # the preceding step in the log, so seq_step is overwritten by "full group".
        logged_step_names = [s.name for s, _process in step_log]
        assert "Start" in logged_step_names
        assert "full group" in logged_step_names
        assert "Final Step" in logged_step_names
        assert "Done" in logged_step_names

        # Verify fork step persisted with correct counts
        fork_step = _get_fork_step(pstat.process_id)
        assert fork_step.parallel_total_branches == 2
        assert fork_step.parallel_completed_count == 2

        # Verify fork step has child_steps via association proxy
        child_steps = list(fork_step.child_steps)
        assert len(child_steps) == 2

        child_names = {cs.name for cs in child_steps}
        assert any("[Branch 0]" in n for n in child_names)
        assert any("[Branch 1]" in n for n in child_names)

        # Verify branch steps are in DB
        all_db_steps = _get_all_steps(pstat.process_id)
        db_step_names = [s.name for s in all_db_steps]
        branch_step_names = [n for n in db_step_names if "[Branch" in n]
        assert len(branch_step_names) >= 2

        # Verify fork step stores initial_state (NOT merged branch results)
        assert fork_step.status == "success"
        assert "cel_a" not in fork_step.state
        assert "cel_b" not in fork_step.state


@pytest.mark.celery
def test_foreach_parallel_worker_dispatches_all_branches() -> None:
    """With EXECUTOR=WORKER, foreach_parallel must dispatch and execute every branch, not just the first."""

    call_log: list[int] = []

    @step("Track FE Item")
    def track_fe_item(item: object, item_index: int) -> dict:
        call_log.append(item_index)
        return {f"tracked_{item_index}": f"done_{item}"}

    @step("Seed FE Items Worker")
    def seed_fe_items_worker() -> dict:
        return {"items": ["x", "y", "z"]}

    @workflow()
    def fe_worker_wf():
        return (
            init >> seed_fe_items_worker >> foreach_parallel("fe worker group", "items", begin >> track_fe_item) >> done
        )

    from orchestrator.services.parallel import run_worker_branch as _original_run_worker_branch

    resume_log: list[object] = []

    def _noop_resume(process, user="test"):
        """Capture resume calls instead of dispatching a real Celery resume task."""
        resume_log.append(process.process_id)

    noop_execution_context = {"start": lambda *a, **kw: None, "resume": _noop_resume, "validate": lambda *a, **kw: None}

    def _scoped_run_worker_branch(**kwargs):
        """Wrap run_worker_branch in database_scope to match production Celery worker isolation.

        In production, each Celery worker task runs with its own DB connection. In tests with
        task_always_eager=True, all tasks share the test connection. The database_scope() ensures
        each branch gets its own session scope, matching the isolation that _execute_branch
        provides in the THREADPOOL path.
        """
        with db.database_scope():
            _original_run_worker_branch(**kwargs)

    with (
        patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER),
        patch("orchestrator.services.parallel.run_worker_branch", _scoped_run_worker_branch),
        # Stub only the resume dispatch so _join_and_resume's DB logic is tested.
        patch("orchestrator.services.processes.get_execution_context", return_value=noop_execution_context),
    ):
        with WorkflowInstanceForTests(fe_worker_wf, "fe_worker_wf"):
            result, pstat, _step_log = run_workflow("fe_worker_wf", [{}])

            # WORKER mode returns Waiting: the parent workflow suspends while branches
            # execute asynchronously. In eager mode the branches have already completed
            # by the time delay() returns, so we verify branch execution via the DB.
            assert result.iswaiting(), f"Expected Waiting (WORKER mode), but was: {result}"

            # All 3 branches must have been called
            assert sorted(call_log) == [0, 1, 2], f"Expected branches 0,1,2 but got {call_log}"

            # DB: fork step must show all branches completed
            fork_step = _get_fork_step(pstat.process_id)
            assert fork_step.parallel_total_branches == 3
            assert fork_step.parallel_completed_count == 3

            # DB: all branch results must be present
            branch_results = _collect_branch_results(fork_step.step_id)
            assert len(branch_results) == 3

            indices = {r[0] for r in branch_results}
            assert indices == {0, 1, 2}

            # Each branch produced its expected key
            all_state_keys = {key for _idx, state, _status in branch_results for key in state}
            assert "tracked_0" in all_state_keys
            assert "tracked_1" in all_state_keys
            assert "tracked_2" in all_state_keys

            # _join_and_resume must have updated the fork step status and triggered resume
            assert fork_step.status == "success"
            assert len(resume_log) == 1, f"Expected exactly 1 resume call, got {len(resume_log)}"
            assert resume_log[0] == pstat.process_id


@pytest.mark.celery
def test_parallel_branch_failure_does_not_retry_with_worker() -> None:
    """A failed parallel branch must result in a Failed workflow, not infinite retries.

    Verifies that:
    1. A workflow with a failing branch reaches terminal Failed state (not Waiting/retrying)
    2. The failing branch is called exactly once (no infinite retry)
    3. Steps after the failed parallel block are not executed

    NOTE: The production retry bug may only manifest with a real Celery worker and
    task_acks_late=True or broker visibility_timeout. This test guards the in-process path.
    DB-level fork step verification is skipped because _create_fork_step's database_scope()
    commit invalidates the shared test connection's transaction when a branch fails.
    """

    fail_call_count = 0
    post_parallel_call_count = 0

    @step("Always Fail")
    def always_fail() -> dict:
        nonlocal fail_call_count
        fail_call_count += 1
        raise RuntimeError("Intentional branch failure")

    @step("Always Succeed")
    def always_succeed() -> dict:
        return {"ok": True}

    @step("After Parallel")
    def after_parallel() -> dict:
        nonlocal post_parallel_call_count
        post_parallel_call_count += 1
        return {"after": True}

    @workflow()
    def fail_worker_wf():
        return init >> parallel("fail group", begin >> always_fail, begin >> always_succeed) >> after_parallel >> done

    from orchestrator.workflows import ALL_WORKFLOWS

    # Register workflow manually to control cleanup (database_scope() commits in
    # _create_fork_step can invalidate the test transaction, making ORM-based cleanup fail).
    from test.unit_tests.workflows import store_workflow

    ALL_WORKFLOWS["fail_worker_wf"] = WorkflowInstanceForTests(fail_worker_wf, "fail_worker_wf")
    wf_table = store_workflow(fail_worker_wf, name="fail_worker_wf")
    try:
        result, pstat, step_log = run_workflow("fail_worker_wf", [{}])

        # Workflow must reach a terminal non-success state
        assert not result.issuccess(), f"Expected failure but got success: {result}"
        assert not result.iswaiting(), f"Workflow stuck in Waiting (retry loop?): {result}"
        assert result.isfailed(), f"Expected Failed but got: {result}"

        # The failing step must have been called exactly once — no retries
        assert fail_call_count == 1, f"Failing branch was called {fail_call_count} times, expected 1"

        # Steps after the failed parallel block must NOT have executed
        assert (
            post_parallel_call_count == 0
        ), f"Post-parallel step was called {post_parallel_call_count} times, expected 0"

        # Verify step log shows the failure propagated from the parallel group
        logged_step_names = [s.name for s, _process in step_log]
        assert (
            "After Parallel" not in logged_step_names
        ), f"After Parallel should not appear in step log: {logged_step_names}"
    finally:
        del ALL_WORKFLOWS["fail_worker_wf"]
        # Clean up DB row; use raw SQL to avoid ObjectDeletedError when the
        # test transaction has been invalidated by _create_fork_step's commit.
        try:
            from sqlalchemy import delete as sa_delete

            from orchestrator.db import WorkflowTable

            db.session.rollback()
            db.session.execute(sa_delete(WorkflowTable).where(WorkflowTable.workflow_id == wf_table.workflow_id))
            db.session.commit()
        except Exception:
            db.session.rollback()

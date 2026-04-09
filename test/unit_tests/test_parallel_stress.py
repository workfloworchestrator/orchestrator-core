"""Stress / integration tests for parallel step execution.

These tests exercise complex compositions of parallel() and foreach_parallel():
nested parallelism, mixed types, asymmetric branches, scale, error propagation,
and edge cases. All tests run with real DB persistence via the engine-pool
session fixture.
"""

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import close_all_sessions, sessionmaker

from orchestrator.db import ProcessStepRelationTable, ProcessStepTable, ProcessTable, db
from orchestrator.db.database import SESSION_ARGUMENTS, BaseModel, SearchQuery
from orchestrator.services.processes import SYSTEM_USER
from orchestrator.workflow import (
    ProcessStat,
    ProcessStatus,
    Success,
    begin,
    done,
    init,
    parallel,
    step,
    workflow,
)
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
    assert_complete,
    run_workflow,
)


@pytest.fixture(autouse=True)
def db_session(database):
    """Use the engine's connection pool so each thread gets its own connection."""
    db.wrapped_database.session_factory = sessionmaker(**SESSION_ARGUMENTS, bind=db.wrapped_database.engine)
    db.wrapped_database.scoped_session = scoped_session(db.session_factory, db._scopefunc)
    BaseModel.set_query(cast(SearchQuery, db.wrapped_database.scoped_session.query_property()))
    try:
        yield
    finally:
        close_all_sessions()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

_wf_counter = 0


def register_test_workflow(wf):
    """Register a workflow for testing and return a WorkflowInstanceForTests context manager."""
    global _wf_counter
    _wf_counter += 1
    return WorkflowInstanceForTests(wf, f"test_parallel_stress_{_wf_counter}")


def create_new_process_stat(wf_table, initial_state):
    """Create a ProcessTable row and return a ProcessStat ready for runwf."""
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
    """Return a step-log callback that appends (step_name, process) tuples to *log*."""

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


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------


def _get_fork_steps(process_id):
    """Return all fork steps for a given process."""
    return (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .all()
    )


def _get_relations(parent_step_id):
    """Return all relation rows for a fork step, ordered by branch_index then order_id."""
    return (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == parent_step_id)
        .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id)
        .all()
    )


# ---------------------------------------------------------------------------
# Step definitions for nested parallel tests
# ---------------------------------------------------------------------------


@step("Outer A")
def outer_a() -> dict:
    return {"outer_a": "done"}


@step("Outer B")
def outer_b() -> dict:
    return {"outer_b": "done"}


@step("Inner X")
def inner_x() -> dict:
    return {"inner_x": "done"}


@step("Inner Y")
def inner_y() -> dict:
    return {"inner_y": "done"}


@step("Deep P")
def deep_p() -> dict:
    return {"deep_p": "done"}


@step("Deep Q")
def deep_q() -> dict:
    return {"deep_q": "done"}


@step("Mid M")
def mid_m() -> dict:
    return {"mid_m": "done"}


@step("Top C")
def top_c() -> dict:
    return {"top_c": "done"}


# ---------------------------------------------------------------------------
# Nested parallel tests
# ---------------------------------------------------------------------------


@pytest.mark.workflow
def test_two_level_nested_parallel() -> None:
    """A parallel block where one branch itself contains a parallel block.

    Structure:
        init >> parallel("Outer",
            begin >> outer_a >> parallel("Inner", begin >> inner_x, begin >> inner_y),
            begin >> outer_b,
        ) >> done

    Verifies:
    - Workflow completes successfully
    - Outer fork step persisted in DB with correct branch count
    - Outer branch steps linked via ProcessStepRelationTable
    - Pre-parallel state is preserved (branch results NOT merged)
    - Inner parallel executes correctly (results visible in branch steps)

    Note: Inner parallel fork steps are not persisted because branch threads
    do not propagate ``process_stat_var``, so ``process_id`` is None inside
    nested parallel branches. Only the outermost fork step is tracked in DB.
    """

    @workflow()
    def nested_2_level_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> outer_a >> parallel("Inner", begin >> inner_x, begin >> inner_y),
                begin >> outer_b,
            )
            >> done
        )

    with WorkflowInstanceForTests(nested_2_level_wf, "nested_2_level_wf"):
        result, pstat, _step_log = run_workflow("nested_2_level_wf", [{}])
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        assert "outer_a" not in state
        assert "outer_b" not in state
        assert "inner_x" not in state
        assert "inner_y" not in state

        # DB: one fork step for "Outer" (inner parallel runs without DB tracking)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        outer_fork = fork_steps[0]
        assert outer_fork.parallel_total_branches == 2
        assert outer_fork.parallel_completed_count == 2

        # Verify outer fork has branch relations with indices {0, 1}
        relations = _get_relations(outer_fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0, 1}

        # Verify that branch steps were created (at least outer_a, outer_b, inner_x, inner_y ran)
        child_step_ids = {rel.child_step_id for rel in relations}
        branch_steps = db.session.query(ProcessStepTable).filter(ProcessStepTable.step_id.in_(child_step_ids)).all()
        # Both branches should have succeeded
        assert all(bs.status == "success" for bs in branch_steps)

        # Branch 0 includes outer_a and the inner parallel; branch 1 is outer_b
        branch_0_rels = [r for r in relations if r.branch_index == 0]
        branch_1_rels = [r for r in relations if r.branch_index == 1]
        # Branch 0 should have more steps (outer_a + inner parallel join step)
        assert len(branch_0_rels) >= 2
        assert len(branch_1_rels) >= 1


@pytest.mark.workflow
def test_three_level_nested_parallel() -> None:
    """Three levels of nesting: parallel inside parallel inside parallel.

    Structure:
        init >> parallel("Top",
            begin >> parallel("Mid",
                begin >> mid_m,
                begin >> parallel("Deep", begin >> deep_p, begin >> deep_q),
            ),
            begin >> top_c,
        ) >> done

    Verifies:
    - Workflow completes successfully
    - Top-level fork step persisted in DB with correct branch count
    - Pre-parallel state is preserved (branch results NOT merged)
    - All nested branches execute without error

    Note: Only the outermost fork step is tracked in DB because branch threads
    do not propagate ``process_stat_var``.
    """

    @workflow()
    def nested_3_level_wf():
        return (
            init
            >> parallel(
                "Top",
                begin >> parallel("Mid", begin >> mid_m, begin >> parallel("Deep", begin >> deep_p, begin >> deep_q)),
                begin >> top_c,
            )
            >> done
        )

    with WorkflowInstanceForTests(nested_3_level_wf, "nested_3_level_wf"):
        result, pstat, _step_log = run_workflow("nested_3_level_wf", [{}])
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        for key in ("mid_m", "deep_p", "deep_q", "top_c"):
            assert key not in state, f"Branch result key {key!r} should not be in main state"

        # DB: one fork step for "Top" (nested parallels run without DB tracking)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        top_fork = fork_steps[0]
        assert top_fork.parallel_total_branches == 2
        assert top_fork.parallel_completed_count == 2

        # Verify top fork has branch relations with indices {0, 1}
        relations = _get_relations(top_fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0, 1}

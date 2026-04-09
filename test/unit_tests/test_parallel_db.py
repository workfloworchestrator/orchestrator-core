"""Integration tests for parallel step DB persistence.

These tests verify that fork steps and branch step relations are
correctly persisted in the database during parallel workflow execution.
"""

import pytest

from orchestrator.db import ProcessStepTable, db
from orchestrator.db.models import ProcessStepRelationTable
from orchestrator.workflow import begin, done, foreach_parallel, init, parallel, step, workflow
from test.unit_tests.workflows import WorkflowInstanceForTests, assert_complete, run_workflow


@step("Int Branch A")
def int_branch_a() -> dict:
    return {"int_a": "done"}


@step("Int Branch B")
def int_branch_b() -> dict:
    return {"int_b": "done"}


@step("Branch A Step 1")
def branch_a1() -> dict:
    return {"a1": "done"}


@step("Branch A Step 2")
def branch_a2(a1: str) -> dict:
    return {"a2": f"{a1}_continued"}


@step("Branch B Step 1")
def branch_b1() -> dict:
    return {"b1": "done"}


@step("Branch B Step 2")
def branch_b2(b1: str) -> dict:
    return {"b2": f"{b1}_continued"}


@step("Process Item")
def process_item(item: object, item_index: int) -> dict:
    return {f"result_{item_index}": f"processed_{item}"}


@step("Pipe Branch X")
def pipe_branch_x() -> dict:
    return {"x": "done"}


@step("Pipe Branch Y")
def pipe_branch_y() -> dict:
    return {"y": "done"}


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


def _get_relations(parent_step_id: object) -> list[ProcessStepRelationTable]:
    """Return all relation rows for a fork step, ordered by branch_index then order_id."""
    return (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == parent_step_id)
        .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id)
        .all()
    )


@pytest.fixture()
def parallel_workflow_run():
    """Run a canonical two-branch parallel workflow and yield (pstat, process_id)."""

    @workflow()
    def parallel_db_wf():
        return init >> parallel("DB test group", begin >> int_branch_a, begin >> int_branch_b) >> done

    with WorkflowInstanceForTests(parallel_db_wf, "parallel_db_wf"):
        result, pstat, _step_log = run_workflow("parallel_db_wf", [{}])
        assert_complete(result)
        yield pstat


@pytest.mark.workflow
def test_fork_step_created_with_branch_count(parallel_workflow_run) -> None:
    pstat = parallel_workflow_run
    fork_steps = (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == pstat.process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .all()
    )
    assert len(fork_steps) == 1
    assert fork_steps[0].parallel_total_branches == 2
    assert fork_steps[0].parallel_completed_count == 2


@pytest.mark.workflow
def test_branch_steps_linked_via_relation_table(parallel_workflow_run) -> None:
    pstat = parallel_workflow_run
    fork_step = _get_fork_step(pstat.process_id)

    relations = _get_relations(fork_step.step_id)
    assert len(relations) >= 2
    branch_indices = {rel.branch_index for rel in relations}
    assert branch_indices == {0, 1}


@pytest.mark.workflow
def test_branch_step_names_include_branch_index(parallel_workflow_run) -> None:
    pstat = parallel_workflow_run
    branch_steps = (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == pstat.process_id,
            ProcessStepTable.name.like("[Branch %]%"),
        )
        .order_by(ProcessStepTable.name)
        .all()
    )
    assert len(branch_steps) >= 2
    names = [s.name for s in branch_steps]
    assert any("[Branch 0]" in n for n in names)
    assert any("[Branch 1]" in n for n in names)


# --- New tests ---


@pytest.mark.workflow
def test_fork_step_status_is_success_after_completion(parallel_workflow_run) -> None:
    """Verify fork step status is 'success' and state is the initial (pre-parallel) state."""
    pstat = parallel_workflow_run
    fork_step = _get_fork_step(pstat.process_id)

    assert fork_step.status == "success"
    assert fork_step.state is not None
    # Fork step stores initial_state, NOT merged branch results
    assert "int_a" not in fork_step.state
    assert "int_b" not in fork_step.state


@pytest.mark.workflow
def test_fork_step_child_steps_via_association_proxy(parallel_workflow_run) -> None:
    """Verify fork_step.child_steps returns branch step objects with correct states."""
    pstat = parallel_workflow_run
    fork_step = _get_fork_step(pstat.process_id)

    child_steps = list(fork_step.child_steps)
    assert len(child_steps) == 2

    child_names = {cs.name for cs in child_steps}
    assert any("[Branch 0]" in n for n in child_names)
    assert any("[Branch 1]" in n for n in child_names)

    for cs in child_steps:
        assert cs.status == "success"
        assert cs.process_id == pstat.process_id


@pytest.mark.workflow
def test_multi_step_branches_create_ordered_relations() -> None:
    """Workflow with 2 branches of 2 steps each creates 4 relation rows with sequential order_ids."""

    @workflow()
    def multi_step_branch_wf():
        return (
            init
            >> parallel("Multi step branches", begin >> branch_a1 >> branch_a2, begin >> branch_b1 >> branch_b2)
            >> done
        )

    with WorkflowInstanceForTests(multi_step_branch_wf, "multi_step_branch_wf"):
        result, pstat, _step_log = run_workflow("multi_step_branch_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)
        relations = _get_relations(fork_step.step_id)

        assert len(relations) == 4

        branch_0_rels = [r for r in relations if r.branch_index == 0]
        branch_1_rels = [r for r in relations if r.branch_index == 1]
        assert len(branch_0_rels) == 2
        assert len(branch_1_rels) == 2

        # order_ids should be sequential within each branch
        branch_0_orders = [r.order_id for r in branch_0_rels]
        branch_1_orders = [r.order_id for r in branch_1_rels]
        assert branch_0_orders == sorted(branch_0_orders)
        assert branch_1_orders == sorted(branch_1_orders)
        assert branch_0_orders[1] == branch_0_orders[0] + 1
        assert branch_1_orders[1] == branch_1_orders[0] + 1


@pytest.mark.workflow
def test_branch_step_states_contain_branch_results(parallel_workflow_run) -> None:
    """Branch step rows contain the state produced by each branch."""
    pstat = parallel_workflow_run
    fork_step = _get_fork_step(pstat.process_id)

    relations = _get_relations(fork_step.step_id)
    child_step_ids = {rel.child_step_id for rel in relations}

    branch_steps = db.session.query(ProcessStepTable).filter(ProcessStepTable.step_id.in_(child_step_ids)).all()
    states = [s.state for s in branch_steps]

    # One branch should have produced int_a, the other int_b
    all_keys = {k for state in states for k in state}
    assert "int_a" in all_keys
    assert "int_b" in all_keys


@pytest.mark.workflow
def test_foreach_parallel_creates_per_item_branch_relations() -> None:
    """foreach_parallel over 3 items creates 3 branches with correct tracking."""

    @step("Seed Items")
    def seed_items() -> dict:
        return {"items": ["alpha", "beta", "gamma"]}

    @workflow()
    def foreach_wf():
        return init >> seed_items >> foreach_parallel("Per item", "items", begin >> process_item) >> done

    with WorkflowInstanceForTests(foreach_wf, "foreach_wf"):
        result, pstat, _step_log = run_workflow("foreach_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)
        assert fork_step.parallel_total_branches == 3
        assert fork_step.parallel_completed_count == 3

        relations = _get_relations(fork_step.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0, 1, 2}


@pytest.mark.workflow
def test_pipe_operator_persists_fork_and_branches() -> None:
    """Using | operator syntax persists fork step with correct branch tracking."""

    @workflow()
    def pipe_wf():
        return init >> ((begin >> pipe_branch_x) | (begin >> pipe_branch_y)) >> done

    with WorkflowInstanceForTests(pipe_wf, "pipe_wf"):
        result, pstat, _step_log = run_workflow("pipe_wf", [{}])
        assert_complete(result)

        fork_step = _get_fork_step(pstat.process_id)
        assert fork_step.parallel_total_branches == 2
        assert fork_step.parallel_completed_count == 2

        relations = _get_relations(fork_step.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0, 1}


@pytest.mark.workflow
def test_cascade_delete_removes_branch_relations(parallel_workflow_run) -> None:
    """Deleting the fork step cascade-deletes all relation rows."""
    pstat = parallel_workflow_run
    fork_step = _get_fork_step(pstat.process_id)
    fork_step_id = fork_step.step_id

    # Verify relations exist before deletion
    relations_before = _get_relations(fork_step_id)
    assert len(relations_before) >= 2

    db.session.delete(fork_step)
    db.session.flush()

    relations_after = (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == fork_step_id)
        .count()
    )
    assert relations_after == 0

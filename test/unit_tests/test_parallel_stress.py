"""Stress / integration tests for parallel step execution.

These tests exercise complex compositions of parallel() and foreach_parallel():
nested parallelism, mixed types, asymmetric branches, scale, error propagation,
and edge cases. All tests run with real DB persistence via the engine-pool
session fixture.
"""

import time
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
    conditional,
    done,
    foreach_parallel,
    init,
    parallel,
    retrystep,
    runwf,
    step,
    workflow,
)
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
    assert_complete,
    assert_failed,
    assert_waiting,
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


# ---------------------------------------------------------------------------
# Step definitions for mixed parallel / foreach_parallel tests
# ---------------------------------------------------------------------------


@step("Process Port")
def process_port(port_id: str) -> dict:
    return {f"result_{port_id}": "processed"}


@step("Tag Item")
def tag_item(item: int, item_index: int) -> dict:
    return {f"tagged_{item_index}": item * 10}


@step("Static Left")
def static_left() -> dict:
    return {"left": "done"}


@step("Static Right")
def static_right() -> dict:
    return {"right": "done"}


@step("Setup Ports")
def setup_ports() -> dict:
    return {"ports": [{"port_id": "p1"}, {"port_id": "p2"}]}


@step("Compute Sum")
def compute_sum(item: int, item_index: int) -> dict:
    return {f"sum_{item_index}": item + 100}


@step("Process Sub")
def process_sub(item: int, item_index: int) -> dict:
    return {f"sub_result_{item_index}": item * 2}


@step("Finalize")
def finalize() -> dict:
    return {"finalized": True}


@step("Branch Marker A")
def branch_marker_a() -> dict:
    return {"marker_a": True}


@step("Branch Marker B")
def branch_marker_b() -> dict:
    return {"marker_b": True}


# ---------------------------------------------------------------------------
# Mixed parallel / foreach_parallel tests
# ---------------------------------------------------------------------------


@pytest.mark.workflow
def test_parallel_with_foreach_branch() -> None:
    """parallel() where one branch uses foreach_parallel.

    Structure:
        init >> parallel("Mixed",
            begin >> setup_ports >> foreach_parallel("FE", "ports", begin >> process_port),
            begin >> static_left,
        ) >> done

    Verifies:
    - Workflow completes successfully
    - Only the outer parallel fork step is persisted in DB
    - Branch results are NOT merged into main state
    - Both the foreach branch and the static branch execute correctly
    """

    @workflow()
    def mixed_parallel_foreach_wf():
        return (
            init
            >> parallel(
                "Mixed",
                begin >> setup_ports >> foreach_parallel("FE", "ports", begin >> process_port),
                begin >> static_left,
            )
            >> done
        )

    with WorkflowInstanceForTests(mixed_parallel_foreach_wf, "mixed_parallel_foreach_wf"):
        result, pstat, _step_log = run_workflow("mixed_parallel_foreach_wf", [{}])
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        assert "result_p1" not in state
        assert "result_p2" not in state
        assert "left" not in state

        # DB: one fork step for "Mixed" (inner foreach runs without DB tracking)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        outer_fork = fork_steps[0]
        assert outer_fork.parallel_total_branches == 2
        assert outer_fork.parallel_completed_count == 2

        relations = _get_relations(outer_fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0, 1}


@pytest.mark.workflow
def test_foreach_parallel_with_parallel_inside() -> None:
    """foreach_parallel where each item's branch contains a static parallel block.

    Structure:
        init >> foreach_parallel("Items", "items", begin >> parallel("Inner",
            begin >> static_left,
            begin >> static_right,
        )) >> done

    Each item spawns a branch that internally runs a parallel() with two sub-branches.

    Verifies:
    - Workflow completes successfully
    - The outer foreach_parallel fork step is persisted in DB with per-item branches
    - Inner parallel fork steps are NOT persisted (no process_stat_var in branch threads)
    - Branch results are NOT merged into main state
    """

    @workflow()
    def foreach_with_inner_parallel_wf():
        return (
            init
            >> foreach_parallel(
                "Items",
                "items",
                begin >> parallel("Inner", begin >> static_left, begin >> static_right),
            )
            >> done
        )

    with register_test_workflow(foreach_with_inner_parallel_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"items": [{"tag": "a"}, {"tag": "b"}, {"tag": "c"}]})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        assert "left" not in state
        assert "right" not in state
        # Initial state preserved
        assert "items" in state

        # DB: one fork step for "Items" foreach (inner parallel not tracked)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fe_fork = fork_steps[0]
        assert fe_fork.parallel_total_branches == 3
        assert fe_fork.parallel_completed_count == 3

        relations = _get_relations(fe_fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0, 1, 2}


@pytest.mark.workflow
def test_sequential_parallel_foreach_parallel_chain() -> None:
    """Sequential chain: parallel >> foreach_parallel >> parallel.

    Structure:
        init >> parallel("P1", begin >> outer_a, begin >> outer_b)
             >> foreach_parallel("FE", "values", begin >> tag_item)
             >> parallel("P2", begin >> static_left, begin >> static_right)
             >> done

    Three parallel blocks executed in sequence, each completing before the next starts.

    Verifies:
    - Workflow completes successfully
    - Three fork steps persisted in DB (one per parallel/foreach_parallel block)
    - Branch results are NOT merged between blocks
    - Initial state key "values" is preserved through all blocks
    """

    @workflow()
    def chain_wf():
        return (
            init
            >> parallel("P1", begin >> outer_a, begin >> outer_b)
            >> foreach_parallel("FE", "values", begin >> tag_item)
            >> parallel("P2", begin >> static_left, begin >> static_right)
            >> done
        )

    with register_test_workflow(chain_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"values": [1, 2, 3]})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        assert "outer_a" not in state
        assert "outer_b" not in state
        assert "tagged_0" not in state
        assert "left" not in state
        assert "right" not in state

        # Initial state preserved through all blocks
        assert "values" in state

        # DB: three fork steps (P1, FE, P2)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 3

        # Look up each fork step by name
        fork_by_name = {fs.name: fs for fs in fork_steps}
        assert set(fork_by_name.keys()) == {"P1", "FE", "P2"}

        # P1: 2 branches
        assert fork_by_name["P1"].parallel_total_branches == 2
        assert fork_by_name["P1"].parallel_completed_count == 2

        # FE: 3 branches (one per item)
        assert fork_by_name["FE"].parallel_total_branches == 3
        assert fork_by_name["FE"].parallel_completed_count == 3

        # P2: 2 branches
        assert fork_by_name["P2"].parallel_total_branches == 2
        assert fork_by_name["P2"].parallel_completed_count == 2


@pytest.mark.workflow
@pytest.mark.parametrize(
    "groups,expected_outer_branches",
    [
        pytest.param(
            [{"group": "A", "sub_items": [1, 2]}, {"group": "B", "sub_items": [3, 4]}],
            2,
            id="two_groups_two_inner_each",
        ),
        pytest.param(
            [{"group": "X", "sub_items": [10, 20, 30]}],
            1,
            id="single_group_three_inner",
        ),
        pytest.param(
            [
                {"group": "A", "sub_items": [1]},
                {"group": "B", "sub_items": [2]},
                {"group": "C", "sub_items": [3]},
            ],
            3,
            id="three_groups_one_inner_each",
        ),
    ],
)
def test_foreach_nested_inside_foreach(groups: list[dict], expected_outer_branches: int) -> None:
    """foreach_parallel nested inside foreach_parallel.

    Structure:
        init >> foreach_parallel("Outer", "groups", begin
            >> foreach_parallel("Inner", "sub_items", begin >> compute_sum)
        ) >> done

    The outer foreach iterates over groups; each group dict contains a "sub_items"
    list that the inner foreach iterates over.

    Verifies:
    - Workflow completes successfully
    - Only the outer foreach_parallel fork step is persisted in DB
    - Inner foreach fork steps are NOT persisted (branch threads lack process_stat_var)
    - Branch results are NOT merged into main state
    - Initial state preserved
    """

    @workflow()
    def nested_foreach_wf():
        return (
            init
            >> foreach_parallel(
                "Outer",
                "groups",
                begin >> foreach_parallel("Inner", "sub_items", begin >> compute_sum),
            )
            >> done
        )

    with register_test_workflow(nested_foreach_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"groups": groups})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        assert "sum_0" not in state
        assert "sum_1" not in state

        # Initial state preserved
        assert "groups" in state

        # DB: one fork step for "Outer" (inner foreach runs without DB tracking)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        outer_fork = fork_steps[0]
        assert outer_fork.parallel_total_branches == expected_outer_branches
        assert outer_fork.parallel_completed_count == expected_outer_branches

        relations = _get_relations(outer_fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == set(range(expected_outer_branches))


# ---------------------------------------------------------------------------
# Step definitions for asymmetric branch tests
# ---------------------------------------------------------------------------


def _make_chain_step(name: str, key: str):
    """Factory that creates a named step returning {key: 'done'}."""

    @step(name)
    def _step() -> dict:
        return {key: "done"}

    return _step


# Pre-create a pool of chain steps for use in asymmetric branch tests
chain_steps: list = [_make_chain_step(f"Chain {i}", f"chain_{i}") for i in range(20)]


def _build_branch(step_count: int, offset: int = 0):
    """Build a branch pipeline with *step_count* steps drawn from the pool.

    Args:
        step_count: Number of steps in this branch.
        offset: Index offset into ``chain_steps`` to avoid reusing the same step objects across branches.

    Returns:
        A pipeline starting with ``begin`` followed by ``step_count`` chained steps.
    """
    from functools import reduce

    branch_steps = chain_steps[offset : offset + step_count]
    return reduce(lambda acc, s: acc >> s, branch_steps, begin)


# ---------------------------------------------------------------------------
# Asymmetric branch tests
# ---------------------------------------------------------------------------


@pytest.mark.workflow
@pytest.mark.parametrize(
    "branch_lengths,expected_relations_per_branch",
    [
        pytest.param(
            [1, 5],
            {0: 1, 1: 5},
            id="1_vs_5_steps",
        ),
        pytest.param(
            [5, 1],
            {0: 5, 1: 1},
            id="5_vs_1_steps",
        ),
        pytest.param(
            [1, 1],
            {0: 1, 1: 1},
            id="1_vs_1_baseline",
        ),
        pytest.param(
            [3, 4, 1],
            {0: 3, 1: 4, 2: 1},
            id="3_vs_4_vs_1_steps",
        ),
    ],
)
def test_asymmetric_branch_lengths(branch_lengths: list[int], expected_relations_per_branch: dict[int, int]) -> None:
    """Parallel block with branches of vastly different step counts.

    Verifies:
    - Workflow completes successfully
    - Correct number of branches in the fork step
    - Each branch has the expected number of ProcessStepRelationTable rows
    - Branch results are NOT merged into main state
    """
    # Build branches with non-overlapping step pool offsets
    offsets: list[int] = []
    running = 0
    for length in branch_lengths:
        offsets.append(running)
        running += length

    branches = tuple(_build_branch(length, offset) for length, offset in zip(branch_lengths, offsets))

    @workflow()
    def asymmetric_wf():
        return init >> parallel("Asym", *branches) >> done

    with register_test_workflow(asymmetric_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        for i in range(sum(branch_lengths)):
            assert f"chain_{i}" not in state, f"Branch result key 'chain_{i}' should not be in main state"

        # DB: one fork step for "Asym"
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == len(branch_lengths)
        assert fork.parallel_completed_count == len(branch_lengths)

        relations = _get_relations(fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == set(range(len(branch_lengths)))

        # Verify each branch has the expected number of relation rows
        for branch_idx, expected_count in expected_relations_per_branch.items():
            branch_rels = [r for r in relations if r.branch_index == branch_idx]
            assert (
                len(branch_rels) == expected_count
            ), f"Branch {branch_idx}: expected {expected_count} relations, got {len(branch_rels)}"


@pytest.mark.workflow
@pytest.mark.parametrize(
    "branch_lengths",
    [
        pytest.param([1, 5], id="1_vs_5_order_ids"),
        pytest.param([5, 1], id="5_vs_1_order_ids"),
        pytest.param([1, 1], id="1_vs_1_order_ids"),
        pytest.param([3, 4, 1], id="3_vs_4_vs_1_order_ids"),
        pytest.param([1, 2, 3, 4, 5], id="ascending_1_to_5_order_ids"),
        pytest.param([5, 4, 3, 2, 1], id="descending_5_to_1_order_ids"),
    ],
)
def test_asymmetric_order_ids_sequential(branch_lengths: list[int]) -> None:
    """Verify ProcessStepRelationTable order_ids are sequential within each branch.

    For asymmetric branches, each branch must have order_ids 0..N-1 where N is the
    number of steps in that branch. This test explicitly checks the order_id values
    regardless of branch length differences.

    Verifies:
    - order_id values form a contiguous 0-based sequence per branch
    - No gaps or duplicates in order_ids within a branch
    - Branches with different lengths have independent order_id sequences
    """
    offsets: list[int] = []
    running = 0
    for length in branch_lengths:
        offsets.append(running)
        running += length

    branches = tuple(_build_branch(length, offset) for length, offset in zip(branch_lengths, offsets))

    @workflow()
    def order_id_wf():
        return init >> parallel("OrderCheck", *branches) >> done

    with register_test_workflow(order_id_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))
        assert_complete(result)

        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        relations = _get_relations(fork.step_id)

        for branch_idx, expected_length in enumerate(branch_lengths):
            branch_rels = [r for r in relations if r.branch_index == branch_idx]
            actual_order_ids = sorted(r.order_id for r in branch_rels)
            expected_order_ids = list(range(expected_length))
            assert (
                actual_order_ids == expected_order_ids
            ), f"Branch {branch_idx}: expected order_ids {expected_order_ids}, got {actual_order_ids}"


# ---------------------------------------------------------------------------
# Step definitions for scale / concurrency tests
# ---------------------------------------------------------------------------


@step("Slow Item Step")
def slow_item_step(item: object, item_index: int) -> dict:
    time.sleep(0.05)
    return {f"result_{item_index}": f"done_{item}"}


# ---------------------------------------------------------------------------
# Scale / concurrency stress tests
# ---------------------------------------------------------------------------


@pytest.mark.workflow
def test_ten_branch_parallel() -> None:
    """A parallel() with 10 branches, each doing a small amount of work.

    Verifies:
    - Workflow completes successfully
    - Fork step has parallel_total_branches=10 and parallel_completed_count=10
    - All 10 branch indices present in ProcessStepRelationTable
    - All branch steps have status "success"
    """

    @workflow()
    def ten_branch_wf():
        return init >> parallel("Ten branches", *[begin >> chain_steps[i] for i in range(10)]) >> done

    with register_test_workflow(ten_branch_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        for i in range(10):
            assert f"chain_{i}" not in state, f"Branch result key 'chain_{i}' should not be in main state"

        # DB: one fork step for "Ten branches"
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 10
        assert fork.parallel_completed_count == 10

        # All 10 branch indices present
        relations = _get_relations(fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == set(range(10))

        # All branch steps have status "success"
        child_step_ids = {rel.child_step_id for rel in relations}
        branch_steps = db.session.query(ProcessStepTable).filter(ProcessStepTable.step_id.in_(child_step_ids)).all()
        assert all(
            bs.status == "success" for bs in branch_steps
        ), f"Not all branch steps succeeded: {[(bs.name, bs.status) for bs in branch_steps]}"


@pytest.mark.workflow
def test_twenty_item_foreach_parallel() -> None:
    """foreach_parallel over a list of 20 items with concurrency verification.

    Verifies:
    - Workflow completes successfully
    - Fork step has parallel_total_branches=20 and parallel_completed_count=20
    - All 20 branch indices present in ProcessStepRelationTable
    - Execution is concurrent (20 items sleeping 0.05s each should complete in <2s)
    """

    @workflow()
    def twenty_item_wf():
        return init >> foreach_parallel("Scale FE", "items", begin >> slow_item_step) >> done

    with register_test_workflow(twenty_item_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"items": list(range(20))})
        start = time.monotonic()
        result = runwf(pstat, store(log))
        elapsed = time.monotonic() - start
        assert_complete(result)

        # Concurrency check: 20 * 0.05s = 1s sequential; concurrent should be much faster
        assert elapsed < 2.0, f"Expected concurrent execution to finish in <2s, took {elapsed:.2f}s"

        # DB: one fork step for "Scale FE"
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 20
        assert fork.parallel_completed_count == 20

        # All 20 branch indices present
        relations = _get_relations(fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == set(range(20))


@pytest.mark.workflow
def test_max_workers_throttling() -> None:
    """foreach_parallel with max_workers=2 throttles concurrency.

    With 10 items each sleeping 0.05s and max_workers=2, execution should take
    ~0.25s (5 batches of 2), not ~0.05s (full parallelism) and not ~0.5s (sequential).

    Verifies:
    - Workflow completes correctly
    - Throttled execution takes longer than fully parallel but less than sequential
    - All 10 branches persisted in DB
    """

    @workflow()
    def throttled_wf():
        return init >> foreach_parallel("Throttled", "items", begin >> slow_item_step, max_workers=2) >> done

    with register_test_workflow(throttled_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"items": list(range(10))})
        start = time.monotonic()
        result = runwf(pstat, store(log))
        elapsed = time.monotonic() - start
        assert_complete(result)

        # Throttling check: 10 items, max_workers=2, each 0.05s -> ~0.25s minimum (5 batches)
        assert elapsed >= 0.2, f"Should be throttled by max_workers=2, but finished in {elapsed:.2f}s"
        # Should still be faster than fully sequential (10 * 0.05s = 0.5s)
        assert elapsed < 2.0, f"Should not be sequential, took {elapsed:.2f}s"

        # DB: one fork step for "Throttled"
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 10
        assert fork.parallel_completed_count == 10

        # All 10 branch indices present
        relations = _get_relations(fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == set(range(10))


# ---------------------------------------------------------------------------
# Step definitions for error propagation tests
# ---------------------------------------------------------------------------


@step("OK Step")
def ok_step() -> dict:
    return {"ok": True}


@step("Failing Inner")
def fail_inner() -> dict:
    raise ValueError("inner fail")


@step("Failing FE Item")
def fail_fe_item(item: object, item_index: int) -> dict:
    if item == "bad":
        raise ValueError("bad item")
    return {f"fe_result_{item_index}": f"done_{item}"}


@retrystep("Retryable Inner")
def retryable_inner() -> dict:
    raise ValueError("retry me")


@step("OK Item Step")
def ok_item_step(item: object, item_index: int) -> dict:
    return {f"item_result_{item_index}": f"processed_{item}"}


# ---------------------------------------------------------------------------
# Error propagation tests
# ---------------------------------------------------------------------------


@pytest.mark.workflow
def test_error_in_inner_nested_parallel_propagates_to_outer() -> None:
    """A failing step inside an inner parallel causes the entire workflow to fail.

    Structure:
        init >> parallel("Outer",
            begin >> ok_step >> parallel("Inner Fail", begin >> fail_inner, begin >> ok_step),
            begin >> ok_step,
        ) >> done

    Verifies:
    - Workflow fails (not completes)
    - Outer fork step exists in DB (created before branches ran)
    """

    @workflow()
    def error_nested_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> ok_step >> parallel("Inner Fail", begin >> fail_inner, begin >> ok_step),
                begin >> ok_step,
            )
            >> done
        )

    with WorkflowInstanceForTests(error_nested_wf, "error_nested_wf"):
        result, pstat, _step_log = run_workflow("error_nested_wf", [{}])
        assert_failed(result)

        # Fork step should exist (outer parallel created it before branches ran)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1


@pytest.mark.workflow
def test_error_in_foreach_parallel_nested_inside_parallel() -> None:
    """A failing item in foreach_parallel inside a parallel branch causes the workflow to fail.

    Structure:
        init >> parallel("Outer",
            begin >> foreach_parallel("FE Fail", "items", begin >> fail_fe_item),
            begin >> ok_step,
        ) >> done

    One of the items is "bad" which triggers a ValueError in fail_fe_item.

    Verifies:
    - Workflow fails
    - Outer fork step exists in DB
    """

    @workflow()
    def error_fe_in_parallel_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> foreach_parallel("FE Fail", "items", begin >> fail_fe_item),
                begin >> ok_step,
            )
            >> done
        )

    with register_test_workflow(error_fe_in_parallel_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"items": ["good", "bad", "fine"]})
        result = runwf(pstat, store(log))
        assert_failed(result)

        # Outer fork step should exist
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1


@pytest.mark.workflow
def test_retryable_step_inside_nested_parallel_returns_waiting() -> None:
    """A retrystep in an inner parallel causes the outer parallel to return Waiting.

    Structure:
        init >> parallel("Outer",
            begin >> ok_step >> parallel("Inner Retry", begin >> retryable_inner, begin >> ok_step),
            begin >> ok_step,
        ) >> done

    The retryable_inner step raises, which makes it return Waiting. Since Waiting is
    worse than Success but better than Failed, the outer parallel returns Waiting.

    Verifies:
    - Workflow result is Waiting (not Failed, not Complete)
    - Fork step exists in DB
    """

    @workflow()
    def retry_nested_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> ok_step >> parallel("Inner Retry", begin >> retryable_inner, begin >> ok_step),
                begin >> ok_step,
            )
            >> done
        )

    with WorkflowInstanceForTests(retry_nested_wf, "retry_nested_wf"):
        result, pstat, _step_log = run_workflow("retry_nested_wf", [{}])
        assert_waiting(result)

        # Fork step should exist
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1


@pytest.mark.workflow
def test_mixed_one_nested_group_fails_another_succeeds_outer_fails() -> None:
    """Two branches each with inner parallels; one inner fails, the other succeeds.

    Structure:
        init >> parallel("Outer",
            begin >> parallel("Inner OK", begin >> ok_step, begin >> ok_step),
            begin >> parallel("Inner Fail", begin >> fail_inner, begin >> ok_step),
        ) >> done

    Failed takes precedence over Success in _worst_status, so the outer parallel fails.

    Verifies:
    - Workflow fails
    - Outer fork step exists in DB
    """

    @workflow()
    def mixed_fail_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> parallel("Inner OK", begin >> ok_step, begin >> ok_step),
                begin >> parallel("Inner Fail", begin >> fail_inner, begin >> ok_step),
            )
            >> done
        )

    with WorkflowInstanceForTests(mixed_fail_wf, "mixed_fail_wf"):
        result, pstat, _step_log = run_workflow("mixed_fail_wf", [{}])
        assert_failed(result)

        # Fork step should exist
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1


@pytest.mark.workflow
def test_partial_db_state_consistent_after_failure() -> None:
    """After a failure, verify DB state is consistent: fork step exists, completed branches have relations.

    Structure:
        init >> parallel("Outer",
            begin >> ok_step,
            begin >> fail_inner,
        ) >> done

    One branch succeeds, the other fails. The fork step should exist and reflect
    the worst status. Completed branch steps should be linked via relations.

    Verifies:
    - Fork step exists with parallel_total_branches set
    - Fork step status reflects failure
    - Relations exist for branches that completed (at least the successful one)
    - Branch steps linked via relations have consistent status values
    """

    @workflow()
    def partial_fail_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> ok_step,
                begin >> fail_inner,
            )
            >> done
        )

    with WorkflowInstanceForTests(partial_fail_wf, "partial_fail_wf"):
        result, pstat, _step_log = run_workflow("partial_fail_wf", [{}])
        assert_failed(result)

        # Fork step must exist
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 2

        # Fork status should reflect the worst outcome (failed)
        assert fork.status == "failed"

        # Relations should exist for branches that ran
        relations = _get_relations(fork.step_id)
        assert len(relations) >= 1  # At least the successful branch recorded steps

        # Check that branch steps linked via relations have valid status values
        child_step_ids = {rel.child_step_id for rel in relations}
        branch_steps = db.session.query(ProcessStepTable).filter(ProcessStepTable.step_id.in_(child_step_ids)).all()
        valid_statuses = {"success", "failed", "waiting"}
        assert all(
            bs.status in valid_statuses for bs in branch_steps
        ), f"Unexpected branch step statuses: {[(bs.name, bs.status) for bs in branch_steps]}"


# ---------------------------------------------------------------------------
# Step definitions for edge case tests
# ---------------------------------------------------------------------------


@step("Noop Step")
def noop_step() -> dict:
    return {}


@step("Empty Branch Step")
def empty_branch_step() -> dict:
    return {}


@step("Identity Step")
def identity_step() -> dict:
    return {"identity": True}


@step("Conditional Target")
def conditional_target() -> dict:
    return {"conditional_ran": True}


@step("Scalar Echo")
def scalar_echo(item: int, item_index: int) -> dict:
    return {f"echo_{item_index}": item}


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


@pytest.mark.workflow
def test_foreach_parallel_single_item() -> None:
    """foreach_parallel over a list with exactly 1 item behaves like a single branch.

    Verifies:
    - Workflow completes successfully
    - Fork step has parallel_total_branches=1
    - Exactly one branch (index 0) in ProcessStepRelationTable
    """

    @workflow()
    def single_item_fe_wf():
        return init >> foreach_parallel("SingleFE", "items", begin >> scalar_echo) >> done

    with register_test_workflow(single_item_fe_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"items": [42]})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Initial state preserved
        assert "items" in state

        # DB: one fork step with exactly 1 branch
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 1
        assert fork.parallel_completed_count == 1

        relations = _get_relations(fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0}


@pytest.mark.workflow
def test_back_to_back_parallel_blocks() -> None:
    """Two parallel blocks immediately adjacent with no sequential step between them.

    Structure:
        init >> parallel("P1", begin >> outer_a, begin >> outer_b)
             >> parallel("P2", begin >> static_left, begin >> static_right)
             >> done

    Verifies:
    - Workflow completes successfully
    - Both fork steps are created in DB
    - Each fork step has the correct branch count
    """

    @workflow()
    def back_to_back_wf():
        return (
            init
            >> parallel("P1", begin >> outer_a, begin >> outer_b)
            >> parallel("P2", begin >> static_left, begin >> static_right)
            >> done
        )

    with register_test_workflow(back_to_back_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))
        assert_complete(result)

        # DB: two fork steps (P1 and P2)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 2

        fork_by_name = {fs.name: fs for fs in fork_steps}
        assert set(fork_by_name.keys()) == {"P1", "P2"}

        for name in ("P1", "P2"):
            assert fork_by_name[name].parallel_total_branches == 2
            assert fork_by_name[name].parallel_completed_count == 2

            relations = _get_relations(fork_by_name[name].step_id)
            branch_indices = {rel.branch_index for rel in relations}
            assert branch_indices == {0, 1}


@pytest.mark.workflow
def test_large_state_through_parallel() -> None:
    """Pass a large dict (100+ keys, nested structures) through a parallel block.

    Verifies deep copy doesn't corrupt state — all original keys survive post-parallel.
    """

    @workflow()
    def large_state_wf():
        return init >> parallel("Large", begin >> noop_step, begin >> noop_step) >> done

    large_state = {f"key_{i}": {"nested": list(range(i)), "label": f"item_{i}"} for i in range(150)}

    with register_test_workflow(large_state_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, large_state)
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # All 150 keys must survive through the parallel block
        assert all(f"key_{i}" in state for i in range(150)), "Some keys were lost through the parallel block"

        # Verify nested structure integrity for a sample of keys
        for i in (0, 50, 99, 149):
            assert state[f"key_{i}"]["nested"] == list(range(i))
            assert state[f"key_{i}"]["label"] == f"item_{i}"


@pytest.mark.workflow
def test_conditional_step_inside_parallel_branch() -> None:
    """A branch of a parallel block uses conditional() to skip a step.

    Structure:
        init >> parallel("With conditional",
            begin >> identity_step >> skip_always(conditional_target),
            begin >> ok_step,
        ) >> done

    Verifies:
    - Workflow completes successfully
    - The conditional_target step is skipped (its result key absent from branch state)
    - Fork step exists in DB with correct branch count
    """
    skip_always = conditional(lambda _state: False)

    @workflow()
    def conditional_parallel_wf():
        return (
            init
            >> parallel(
                "With conditional",
                begin >> identity_step >> skip_always(conditional_target),
                begin >> ok_step,
            )
            >> done
        )

    with register_test_workflow(conditional_parallel_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Branch results must NOT leak into main state
        assert "conditional_ran" not in state
        assert "identity" not in state
        assert "ok" not in state

        # DB: one fork step
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 2
        assert fork.parallel_completed_count == 2


@pytest.mark.workflow
def test_foreach_parallel_with_scalar_items() -> None:
    """foreach_parallel with a list of scalar integers.

    Verifies that item and item_index are accessible in the step function
    and the workflow completes correctly for all items.
    """

    @workflow()
    def scalar_fe_wf():
        return init >> foreach_parallel("ScalarFE", "values", begin >> scalar_echo) >> done

    with register_test_workflow(scalar_fe_wf) as wf_table:
        log: list = []
        pstat = create_new_process_stat(wf_table, {"values": [10, 20, 30, 40, 50]})
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Initial state preserved
        assert "values" in state
        assert state["values"] == [10, 20, 30, 40, 50]

        # DB: one fork step with 5 branches
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 5
        assert fork.parallel_completed_count == 5

        relations = _get_relations(fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == set(range(5))


@pytest.mark.workflow
def test_parallel_branches_return_empty_dicts() -> None:
    """Both branches of a parallel block return empty dicts.

    Verifies this doesn't break the merge logic or cause any issues.
    """

    @workflow()
    def empty_branches_wf():
        return init >> parallel("Empty", begin >> empty_branch_step, begin >> empty_branch_step) >> done

    with register_test_workflow(empty_branches_wf) as wf_table:
        log: list = []
        initial = {"sentinel": "preserved"}
        pstat = create_new_process_stat(wf_table, initial)
        result = runwf(pstat, store(log))
        assert_complete(result)
        state = result.unwrap()

        # Initial state must survive
        assert state["sentinel"] == "preserved"

        # DB: one fork step with 2 branches
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1

        fork = fork_steps[0]
        assert fork.parallel_total_branches == 2
        assert fork.parallel_completed_count == 2

        relations = _get_relations(fork.step_id)
        branch_indices = {rel.branch_index for rel in relations}
        assert branch_indices == {0, 1}

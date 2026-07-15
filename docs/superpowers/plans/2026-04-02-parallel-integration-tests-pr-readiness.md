# Parallel Execution: Integration Tests & PR Readiness

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close test coverage gaps with real DB and Celery integration tests, fix remaining issues, and get the `parallel-step-design` branch PR-ready.

**Architecture:** The parallel execution implementation is complete across `orchestrator/workflow.py` (DSL, ThreadPool executor, join logic), `orchestrator/services/parallel.py` (Celery branch execution), and `orchestrator/db/models.py` (ProcessStepRelationTable, fork step columns). This plan adds integration tests that exercise real DB persistence and real Celery task dispatch, fixes deprecation warnings, and ensures all code paths are covered.

**Tech Stack:** pytest, SQLAlchemy (real DB sessions), Celery (pytest-celery with `task_always_eager=True`), orchestrator workflow engine

---

## File Structure

| File | Responsibility |
|------|---------------|
| `test/unit_tests/test_parallel_db.py` | **Expand** — DB persistence integration tests (fork steps, branch relations, foreach, failures, multi-step branches, association proxy) |
| `test/integration_tests/test_parallel_celery_integration.py` | **Create** — Real Celery integration tests (branch dispatch, atomic join, last-finisher resume, failure propagation, queue routing) |
| `test/unit_tests/test_parallel_workflow.py` | **Fix** — Remove deprecation warnings (`workflow("name")` → `workflow()`) |
| `test/unit_tests/test_parallel_join.py` | **Verify** — Already has good coverage, may need minor additions |
| `test/integration_tests/conftest.py` | **Extend** — Add parallel branch Celery task registration fixture |

---

## Task 1: Fix Deprecation Warnings in test_parallel_workflow.py

The `workflow("description")` pattern is deprecated. All test workflows should use `workflow()` without a description string. There are ~25 instances producing 69 warnings.

**Files:**
- Modify: `test/unit_tests/test_parallel_workflow.py`

- [ ] **Step 1: Fix all workflow() calls to remove description parameter**

Replace every `workflow("Some Name")` with `workflow()` throughout the file. The affected patterns are:

```python
# BEFORE (deprecated):
wf = workflow("Pipe WF")(lambda: ...)
wf = workflow("Dict WF")(lambda: ...)
# ... etc

# AFTER:
wf = workflow()(lambda: ...)
```

Affected lines (approximate): 146, 163, 183, 224, 243, 267, 283, 316, 334, 347, 358, 377, 441, 465, 488, 509, 539, 561, 575, 603, 613, 639, 669, 699, 725, 756, 782, 802, 845, 863, 881, 898, 916, 937.

Note: Line 823 already uses `workflow()` without description — that's the correct pattern.

- [ ] **Step 2: Run tests to verify no regressions and warnings are gone**

Run: `uv run pytest test/unit_tests/test_parallel_workflow.py -q --no-header -W error::DeprecationWarning 2>&1 | tail -5`
Expected: All tests pass with zero deprecation warnings.

- [ ] **Step 3: Commit**

```bash
git add test/unit_tests/test_parallel_workflow.py
git commit -m "Fix deprecation warnings: remove description param from workflow() in parallel tests"
```

---

## Task 2: Expand DB Integration Tests (test_parallel_db.py)

The current file has only 3 tests using a single fixture. We need thorough coverage of DB persistence for all parallel scenarios.

**Files:**
- Modify: `test/unit_tests/test_parallel_db.py`
- Reference: `test/unit_tests/workflows/__init__.py` (WorkflowInstanceForTests, run_workflow, assert_*)

- [ ] **Step 1: Add test for fork step status after successful completion**

Verify that the fork step's `status` is set to `"success"` and `state` contains merged branch results after a successful parallel run.

```python
@pytest.mark.workflow
def test_fork_step_status_is_success_after_completion(parallel_workflow_run) -> None:
    """Fork step status should be 'success' after all branches complete."""
    pstat = parallel_workflow_run
    fork_step = (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == pstat.process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .one()
    )
    assert fork_step.status == "success"
    assert "int_a" in fork_step.state
    assert "int_b" in fork_step.state
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_db.py::test_fork_step_status_is_success_after_completion -v`
Expected: PASS

- [ ] **Step 3: Add test for association_proxy child_steps access**

Verify that `fork_step.child_steps` returns the branch step objects (tests the association proxy defined in models.py).

```python
@pytest.mark.workflow
def test_fork_step_child_steps_via_association_proxy(parallel_workflow_run) -> None:
    """Fork step's child_steps association proxy returns branch step objects."""
    pstat = parallel_workflow_run
    fork_step = (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == pstat.process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .one()
    )
    child_steps = list(fork_step.child_steps)
    assert len(child_steps) == 2
    child_states = [cs.state for cs in child_steps]
    assert any("int_a" in s for s in child_states)
    assert any("int_b" in s for s in child_states)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_db.py::test_fork_step_child_steps_via_association_proxy -v`
Expected: PASS

- [ ] **Step 5: Add test for multi-step branches creating multiple relation rows**

Each step in a branch should create its own relation row. A branch with 2 steps should produce 2 relation rows with sequential order_ids.

```python
@step("Multi A1")
def multi_a1() -> dict:
    return {"ma1": "done"}


@step("Multi A2")
def multi_a2(ma1: str) -> dict:
    return {"ma2": f"{ma1}_continued"}


@step("Multi B1")
def multi_b1() -> dict:
    return {"mb1": "done"}


@step("Multi B2")
def multi_b2(mb1: str) -> dict:
    return {"mb2": f"{mb1}_continued"}


@pytest.mark.workflow
def test_multi_step_branches_create_ordered_relations() -> None:
    """Multi-step branches create multiple relation rows with sequential order_ids."""

    @workflow()
    def multi_step_db_wf():
        return init >> parallel("Multi step group", begin >> multi_a1 >> multi_a2, begin >> multi_b1 >> multi_b2) >> done

    with WorkflowInstanceForTests(multi_step_db_wf, "multi_step_db_wf"):
        result, pstat, _step_log = run_workflow("multi_step_db_wf", [{}])
        assert_complete(result)

        fork_step = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == pstat.process_id,
                ProcessStepTable.parallel_total_branches.isnot(None),
            )
            .one()
        )

        relations = (
            db.session.query(ProcessStepRelationTable)
            .filter(ProcessStepRelationTable.parent_step_id == fork_step.step_id)
            .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id)
            .all()
        )
        # 2 branches x 2 steps each = 4 relations
        assert len(relations) == 4

        branch_0 = [r for r in relations if r.branch_index == 0]
        branch_1 = [r for r in relations if r.branch_index == 1]
        assert len(branch_0) == 2
        assert len(branch_1) == 2
        # Order IDs are sequential within each branch
        assert branch_0[0].order_id < branch_0[1].order_id
        assert branch_1[0].order_id < branch_1[1].order_id
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_db.py::test_multi_step_branches_create_ordered_relations -v`
Expected: PASS

- [ ] **Step 7: Add test for failed branch DB persistence**

When one branch fails, both branches should still have their steps persisted, and the fork step should reflect failure.

```python
@step("Good DB branch")
def good_db_branch() -> dict:
    return {"good": True}


@step("Bad DB branch")
def bad_db_branch() -> dict:
    raise ValueError("branch exploded")


@pytest.mark.workflow
def test_failed_branch_steps_persisted() -> None:
    """Both branches are persisted even when one fails; fork step reflects failure."""

    @workflow()
    def failed_branch_db_wf():
        return init >> parallel("Fail group", begin >> good_db_branch, begin >> bad_db_branch) >> done

    with WorkflowInstanceForTests(failed_branch_db_wf, "failed_branch_db_wf"):
        result, pstat, _step_log = run_workflow("failed_branch_db_wf", [{}])
        assert_failed(result)

        fork_step = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == pstat.process_id,
                ProcessStepTable.parallel_total_branches.isnot(None),
            )
            .one()
        )
        assert fork_step.status == "failed"

        relations = (
            db.session.query(ProcessStepRelationTable)
            .filter(ProcessStepRelationTable.parent_step_id == fork_step.step_id)
            .all()
        )
        assert len(relations) == 2
        assert {r.branch_index for r in relations} == {0, 1}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_db.py::test_failed_branch_steps_persisted -v`
Expected: PASS

- [ ] **Step 9: Add test for foreach_parallel DB persistence**

Verify that `foreach_parallel` creates one fork step with N branches (one per item), each linked via relations.

```python
@step("Provision DB port")
def provision_db_port(port_id: str) -> dict:
    return {f"result_{port_id}": "provisioned"}


@step("Setup DB ports")
def setup_db_ports() -> dict:
    return {"ports": [{"port_id": "p1"}, {"port_id": "p2"}, {"port_id": "p3"}]}


@pytest.mark.workflow
def test_foreach_parallel_creates_per_item_branch_relations() -> None:
    """foreach_parallel creates one fork step with N branch relations (one per item)."""

    @workflow()
    def foreach_db_wf():
        return init >> setup_db_ports >> foreach_parallel("Provision ports", "ports", begin >> provision_db_port) >> done

    with WorkflowInstanceForTests(foreach_db_wf, "foreach_db_wf"):
        result, pstat, _step_log = run_workflow("foreach_db_wf", [{}])
        assert_complete(result)

        fork_step = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == pstat.process_id,
                ProcessStepTable.parallel_total_branches.isnot(None),
            )
            .one()
        )
        assert fork_step.parallel_total_branches == 3
        assert fork_step.parallel_completed_count == 3

        relations = (
            db.session.query(ProcessStepRelationTable)
            .filter(ProcessStepRelationTable.parent_step_id == fork_step.step_id)
            .all()
        )
        assert len(relations) == 3
        assert {r.branch_index for r in relations} == {0, 1, 2}
```

- [ ] **Step 10: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_db.py::test_foreach_parallel_creates_per_item_branch_relations -v`
Expected: PASS

- [ ] **Step 11: Add test for pipe operator syntax DB persistence**

Verify that the `|` operator syntax (not just `parallel()`) correctly persists fork/branch steps.

```python
@pytest.mark.workflow
def test_pipe_operator_persists_fork_and_branches() -> None:
    """| operator syntax persists fork step and branch relations identically to parallel()."""

    @workflow()
    def pipe_db_wf():
        return init >> {"Pipe group": (begin >> int_branch_a) | (begin >> int_branch_b)} >> done

    with WorkflowInstanceForTests(pipe_db_wf, "pipe_db_wf"):
        result, pstat, _step_log = run_workflow("pipe_db_wf", [{}])
        assert_complete(result)

        fork_step = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == pstat.process_id,
                ProcessStepTable.parallel_total_branches.isnot(None),
            )
            .one()
        )
        assert fork_step.name == "Pipe group"
        assert fork_step.parallel_total_branches == 2
        assert fork_step.parallel_completed_count == 2
```

- [ ] **Step 12: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_db.py::test_pipe_operator_persists_fork_and_branches -v`
Expected: PASS

- [ ] **Step 13: Add test for cascade delete behavior**

When a fork step is deleted, its child relations and child steps should be cascade-deleted.

```python
@pytest.mark.workflow
def test_cascade_delete_removes_branch_relations(parallel_workflow_run) -> None:
    """Deleting a fork step cascades to ProcessStepRelationTable entries."""
    pstat = parallel_workflow_run
    fork_step = (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == pstat.process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .one()
    )
    fork_step_id = fork_step.step_id

    # Confirm relations exist before delete
    relations_before = (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == fork_step_id)
        .count()
    )
    assert relations_before == 2

    db.session.delete(fork_step)
    db.session.flush()

    relations_after = (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == fork_step_id)
        .count()
    )
    assert relations_after == 0
```

- [ ] **Step 14: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_db.py::test_cascade_delete_removes_branch_relations -v`
Expected: PASS

- [ ] **Step 15: Run full DB test suite**

Run: `uv run pytest test/unit_tests/test_parallel_db.py -v`
Expected: All tests pass.

- [ ] **Step 16: Commit**

```bash
git add test/unit_tests/test_parallel_db.py
git commit -m "Add comprehensive DB integration tests for parallel execution"
```

---

## Task 3: Register Parallel Branch Celery Tasks in Integration Test Fixtures

The integration test conftest needs to register `EXECUTE_PARALLEL_BRANCH` and `EXECUTE_PARALLEL_BRANCH_WORKFLOW` tasks so Celery knows how to dispatch them.

**Files:**
- Modify: `test/integration_tests/conftest.py`
- Reference: `orchestrator/services/tasks.py` (task constants, `_run_parallel_branch` implementation)
- Reference: `orchestrator/services/parallel.py` (`run_celery_branch`)

- [ ] **Step 1: Add parallel branch task constants to imports**

Add the parallel branch task imports at the top of `test/integration_tests/conftest.py`:

```python
from orchestrator.services.tasks import (
    EXECUTE_PARALLEL_BRANCH,
    EXECUTE_PARALLEL_BRANCH_WORKFLOW,
    NEW_TASK,
    NEW_WORKFLOW,
    RESUME_TASK,
    RESUME_WORKFLOW,
    initialise_celery,
    register_custom_serializer,
)
```

- [ ] **Step 2: Add parallel branch queue routing to celery_config**

Add the parallel branch task routes to the `celery_config` fixture's `task_routes` dict:

```python
"task_routes": {
    NEW_TASK: {"queue": "test_tasks"},
    NEW_WORKFLOW: {"queue": "test_workflows"},
    RESUME_TASK: {"queue": "test_tasks"},
    RESUME_WORKFLOW: {"queue": "test_workflows"},
    EXECUTE_PARALLEL_BRANCH: {"queue": "test_tasks"},
    EXECUTE_PARALLEL_BRANCH_WORKFLOW: {"queue": "test_workflows"},
},
```

- [ ] **Step 3: Register parallel branch tasks in register_celery_tasks fixture**

Add the parallel branch task registrations to the `register_celery_tasks` fixture:

```python
@celery_session_app.task(name=EXECUTE_PARALLEL_BRANCH)
def execute_parallel_branch(*, process_id: str, branch_index: int, fork_step_id: str, initial_state: dict, user: str = "test") -> str:
    from uuid import UUID

    from orchestrator.services.parallel import run_celery_branch

    run_celery_branch(
        process_id=UUID(process_id),
        branch_index=branch_index,
        fork_step_id=UUID(fork_step_id),
        initial_state=initial_state,
        user=user,
    )
    return f"Executed branch {branch_index} of {process_id}"

tasks[EXECUTE_PARALLEL_BRANCH] = execute_parallel_branch

@celery_session_app.task(name=EXECUTE_PARALLEL_BRANCH_WORKFLOW)
def execute_parallel_branch_workflow(*, process_id: str, branch_index: int, fork_step_id: str, initial_state: dict, user: str = "test") -> str:
    from uuid import UUID

    from orchestrator.services.parallel import run_celery_branch

    run_celery_branch(
        process_id=UUID(process_id),
        branch_index=branch_index,
        fork_step_id=UUID(fork_step_id),
        initial_state=initial_state,
        user=user,
    )
    return f"Executed branch workflow {branch_index} of {process_id}"

tasks[EXECUTE_PARALLEL_BRANCH_WORKFLOW] = execute_parallel_branch_workflow
```

- [ ] **Step 4: Run existing Celery integration tests to verify no regressions**

Run: `uv run pytest test/integration_tests/test_with_pytest_celery.py -v -m celery`
Expected: All existing Celery tests still pass.

- [ ] **Step 5: Commit**

```bash
git add test/integration_tests/conftest.py
git commit -m "Register parallel branch Celery tasks in integration test fixtures"
```

---

## Task 4: Create Celery Integration Tests for Parallel Branch Execution

These tests exercise the real Celery dispatch path with `task_always_eager=True`, real DB persistence, and real `run_celery_branch` execution.

**Files:**
- Create: `test/integration_tests/test_parallel_celery_integration.py`
- Reference: `test/integration_tests/conftest.py` (fixtures)
- Reference: `test/integration_tests/test_with_pytest_celery.py` (patterns)
- Reference: `orchestrator/services/parallel.py` (run_celery_branch, _atomic_increment_completed, _collect_branch_results, _celery_join_and_resume)
- Reference: `orchestrator/workflow.py` (_exec_parallel_branches_celery, _create_fork_step)

- [ ] **Step 1: Write the test file skeleton with shared fixtures and helpers**

```python
"""Integration tests for Celery-based parallel branch execution.

These tests use task_always_eager=True for synchronous Celery execution,
but exercise the real run_celery_branch, atomic join counter, and
last-finisher resume path with a real database.
"""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from orchestrator.db import ProcessStepTable, ProcessTable, WorkflowTable, db
from orchestrator.db.models import ProcessStepRelationTable
from orchestrator.services.parallel import (
    _atomic_increment_completed,
    _collect_branch_results,
    run_celery_branch,
)
from orchestrator.settings import ExecutorType
from orchestrator.targets import Target
from orchestrator.workflow import (
    ProcessStatus,
    Success,
    begin,
    done,
    foreach_parallel,
    init,
    parallel,
    step,
    workflow,
)
from test.unit_tests.workflows import WorkflowInstanceForTests, assert_complete, assert_failed, run_workflow


# --- Shared step definitions ---


@step("Celery Branch A")
def celery_branch_a() -> dict:
    return {"celery_a": "done"}


@step("Celery Branch B")
def celery_branch_b() -> dict:
    return {"celery_b": "done"}


@step("Celery Branch A1")
def celery_branch_a1() -> dict:
    return {"celery_a1": "step1"}


@step("Celery Branch A2")
def celery_branch_a2(celery_a1: str) -> dict:
    return {"celery_a2": f"{celery_a1}_step2"}


@step("Celery Failing Branch")
def celery_failing_branch() -> dict:
    raise ValueError("celery branch exploded")


@step("Celery Provision Port")
def celery_provision_port(port_id: str) -> dict:
    return {f"celery_result_{port_id}": "provisioned"}


# --- Query helpers ---


def get_fork_step(process_id: UUID) -> ProcessStepTable:
    return (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .one()
    )


def get_branch_relations(fork_step_id: UUID) -> list[ProcessStepRelationTable]:
    return (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == fork_step_id)
        .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id)
        .all()
    )
```

- [ ] **Step 2: Add test for atomic_increment_completed with real DB**

```python
@pytest.mark.celery
@pytest.mark.workflow
def test_atomic_increment_completed_with_real_db() -> None:
    """_atomic_increment_completed atomically increments counter in real DB."""

    @workflow()
    def atomic_test_wf():
        return init >> parallel("Atomic group", begin >> celery_branch_a, begin >> celery_branch_b) >> done

    with WorkflowInstanceForTests(atomic_test_wf, "atomic_test_wf"):
        result, pstat, _ = run_workflow("atomic_test_wf", [{}])
        assert_complete(result)

        fork_step = get_fork_step(pstat.process_id)

        # Fork step should already have completed_count == total after ThreadPool run
        assert fork_step.parallel_completed_count == 2
        assert fork_step.parallel_total_branches == 2

        # Now test the atomic increment function directly on this fork step
        # Reset counter to test increment
        fork_step.parallel_completed_count = 0
        db.session.commit()

        completed_1, total_1 = _atomic_increment_completed(fork_step.step_id)
        assert completed_1 == 1
        assert total_1 == 2

        completed_2, total_2 = _atomic_increment_completed(fork_step.step_id)
        assert completed_2 == 2
        assert total_2 == 2
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_atomic_increment_completed_with_real_db -v`
Expected: PASS

- [ ] **Step 4: Add test for _collect_branch_results with real DB**

```python
@pytest.mark.celery
@pytest.mark.workflow
def test_collect_branch_results_from_real_db() -> None:
    """_collect_branch_results retrieves correct branch states from DB."""

    @workflow()
    def collect_test_wf():
        return init >> parallel("Collect group", begin >> celery_branch_a, begin >> celery_branch_b) >> done

    with WorkflowInstanceForTests(collect_test_wf, "collect_test_wf"):
        result, pstat, _ = run_workflow("collect_test_wf", [{}])
        assert_complete(result)

        fork_step = get_fork_step(pstat.process_id)
        branch_data = _collect_branch_results(fork_step.step_id)

        assert len(branch_data) == 2
        branch_indices = [bd[0] for bd in branch_data]
        assert sorted(branch_indices) == [0, 1]

        # Each branch should have its state
        states = {bd[0]: bd[1] for bd in branch_data}
        assert any("celery_a" in s for s in states.values())
        assert any("celery_b" in s for s in states.values())

        # All should be success status
        statuses = [bd[2] for bd in branch_data]
        assert all(s == "success" for s in statuses)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_collect_branch_results_from_real_db -v`
Expected: PASS

- [ ] **Step 6: Add test for run_celery_branch with real DB and workflow**

This is the core test — run a single branch through the Celery branch execution path with real DB persistence, verifying branch steps are written and the atomic counter increments.

```python
@pytest.mark.celery
@pytest.mark.workflow
def test_run_celery_branch_persists_steps_and_increments_counter() -> None:
    """run_celery_branch writes branch steps to DB and increments atomic counter."""

    @workflow()
    def celery_branch_run_wf():
        return init >> parallel("Branch run group", begin >> celery_branch_a, begin >> celery_branch_b) >> done

    with WorkflowInstanceForTests(celery_branch_run_wf, "celery_branch_run_wf"):
        # First, create the process and workflow table entry manually
        # so we can call run_celery_branch directly
        wf_table = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "celery_branch_run_wf"))
        assert wf_table is not None

        process = ProcessTable(
            workflow_id=wf_table.workflow_id,
            last_status=ProcessStatus.RUNNING,
            assignee=Target.SYSTEM,
            process_id=uuid4(),
        )
        db.session.add(process)
        db.session.flush()

        # Create a fork step manually
        fork_step = ProcessStepTable(
            process_id=process.process_id,
            name="Branch run group",
            status="pending",
            state={},
            created_by="test",
            parallel_total_branches=2,
            parallel_completed_count=0,
        )
        db.session.add(fork_step)
        db.session.commit()

        # Execute branch 0 directly
        run_celery_branch(
            process_id=process.process_id,
            branch_index=0,
            fork_step_id=fork_step.step_id,
            initial_state={},
            user="test",
        )

        # Verify branch 0 step was persisted
        relations = get_branch_relations(fork_step.step_id)
        branch_0_relations = [r for r in relations if r.branch_index == 0]
        assert len(branch_0_relations) == 1

        # Verify atomic counter was incremented
        db.session.refresh(fork_step)
        assert fork_step.parallel_completed_count == 1

        # Execute branch 1
        run_celery_branch(
            process_id=process.process_id,
            branch_index=1,
            fork_step_id=fork_step.step_id,
            initial_state={},
            user="test",
        )

        # Verify branch 1 step was persisted
        relations = get_branch_relations(fork_step.step_id)
        branch_1_relations = [r for r in relations if r.branch_index == 1]
        assert len(branch_1_relations) == 1

        # Verify counter reached total (last-finisher detection)
        db.session.refresh(fork_step)
        assert fork_step.parallel_completed_count == 2
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_run_celery_branch_persists_steps_and_increments_counter -v`
Expected: PASS

- [ ] **Step 8: Add test for multi-step branch via run_celery_branch**

```python
@pytest.mark.celery
@pytest.mark.workflow
def test_run_celery_branch_multi_step_creates_ordered_relations() -> None:
    """A multi-step branch creates multiple relation rows with correct ordering."""

    @workflow()
    def celery_multi_step_wf():
        return (
            init
            >> parallel("Multi step group", begin >> celery_branch_a1 >> celery_branch_a2, begin >> celery_branch_b)
            >> done
        )

    with WorkflowInstanceForTests(celery_multi_step_wf, "celery_multi_step_wf"):
        wf_table = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "celery_multi_step_wf"))

        process = ProcessTable(
            workflow_id=wf_table.workflow_id,
            last_status=ProcessStatus.RUNNING,
            assignee=Target.SYSTEM,
            process_id=uuid4(),
        )
        db.session.add(process)
        db.session.flush()

        fork_step = ProcessStepTable(
            process_id=process.process_id,
            name="Multi step group",
            status="pending",
            state={},
            created_by="test",
            parallel_total_branches=2,
            parallel_completed_count=0,
        )
        db.session.add(fork_step)
        db.session.commit()

        # Execute branch 0 (has 2 steps: a1 >> a2)
        run_celery_branch(
            process_id=process.process_id,
            branch_index=0,
            fork_step_id=fork_step.step_id,
            initial_state={},
            user="test",
        )

        branch_0_relations = [r for r in get_branch_relations(fork_step.step_id) if r.branch_index == 0]
        assert len(branch_0_relations) == 2
        assert branch_0_relations[0].order_id < branch_0_relations[1].order_id

        # Verify the final branch state contains results from both steps
        last_step = branch_0_relations[-1].child_step
        assert "celery_a1" in last_step.state
        assert "celery_a2" in last_step.state
```

- [ ] **Step 9: Run test to verify it passes**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_run_celery_branch_multi_step_creates_ordered_relations -v`
Expected: PASS

- [ ] **Step 10: Add test for failing branch via run_celery_branch**

```python
@pytest.mark.celery
@pytest.mark.workflow
def test_run_celery_branch_failure_still_increments_counter() -> None:
    """A failing branch still increments the completed counter (for last-finisher detection)."""

    @workflow()
    def celery_fail_wf():
        return init >> parallel("Fail group", begin >> celery_branch_a, begin >> celery_failing_branch) >> done

    with WorkflowInstanceForTests(celery_fail_wf, "celery_fail_wf"):
        wf_table = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "celery_fail_wf"))

        process = ProcessTable(
            workflow_id=wf_table.workflow_id,
            last_status=ProcessStatus.RUNNING,
            assignee=Target.SYSTEM,
            process_id=uuid4(),
        )
        db.session.add(process)
        db.session.flush()

        fork_step = ProcessStepTable(
            process_id=process.process_id,
            name="Fail group",
            status="pending",
            state={},
            created_by="test",
            parallel_total_branches=2,
            parallel_completed_count=0,
        )
        db.session.add(fork_step)
        db.session.commit()

        # Execute the failing branch (should not crash, should increment counter)
        run_celery_branch(
            process_id=process.process_id,
            branch_index=1,
            fork_step_id=fork_step.step_id,
            initial_state={},
            user="test",
        )

        db.session.refresh(fork_step)
        assert fork_step.parallel_completed_count == 1

        # The branch step should be persisted with failed status
        relations = get_branch_relations(fork_step.step_id)
        assert len(relations) >= 1
```

- [ ] **Step 11: Run test to verify it passes**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_run_celery_branch_failure_still_increments_counter -v`
Expected: PASS

- [ ] **Step 12: Add test for foreach_parallel via Celery dispatch path**

Test the full foreach_parallel path through the Celery executor by setting `EXECUTOR=WORKER` and running via `run_workflow`. With `task_always_eager=True`, branches execute synchronously but through the real Celery task path.

```python
@pytest.mark.celery
@pytest.mark.workflow
def test_foreach_parallel_celery_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """foreach_parallel dispatches per-item branches through Celery when EXECUTOR=WORKER."""
    monkeypatch.setattr("orchestrator.settings.app_settings.EXECUTOR", ExecutorType.WORKER)

    @step("Setup Celery ports")
    def setup_celery_ports() -> dict:
        return {"ports": [{"port_id": "cp1"}, {"port_id": "cp2"}]}

    @workflow()
    def foreach_celery_wf():
        return init >> setup_celery_ports >> foreach_parallel("Celery ports", "ports", begin >> celery_provision_port) >> done

    with WorkflowInstanceForTests(foreach_celery_wf, "foreach_celery_wf"):
        result, pstat, _ = run_workflow("foreach_celery_wf", [{}])

        # With Celery dispatch, the initial run returns Waiting
        # The branches execute synchronously (task_always_eager) and join
        # Final result depends on whether the eager Celery tasks trigger the resume path
        fork_step = get_fork_step(pstat.process_id)
        assert fork_step.parallel_total_branches == 2

        relations = get_branch_relations(fork_step.step_id)
        assert len(relations) == 2
        assert {r.branch_index for r in relations} == {0, 1}
```

- [ ] **Step 13: Run test to verify it passes**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_foreach_parallel_celery_dispatch -v`
Expected: PASS (or needs debugging — the eager Celery + resume path may need adjustment)

- [ ] **Step 14: Add test for _resolve_branch_from_db with real DB**

```python
@pytest.mark.celery
@pytest.mark.workflow
def test_resolve_branch_from_db_finds_correct_branch() -> None:
    """_resolve_branch_from_db correctly resolves workflow and branch from fork step."""
    from orchestrator.services.parallel import _resolve_branch_from_db

    @workflow()
    def resolve_test_wf():
        return init >> parallel("Resolve group", begin >> celery_branch_a, begin >> celery_branch_b) >> done

    with WorkflowInstanceForTests(resolve_test_wf, "resolve_test_wf"):
        result, pstat, _ = run_workflow("resolve_test_wf", [{}])
        assert_complete(result)

        fork_step = get_fork_step(pstat.process_id)

        # Resolve branch 0
        name_0, branch_0 = _resolve_branch_from_db(fork_step.step_id, pstat.process_id, 0)
        assert name_0 == "Resolve group"
        assert len(branch_0) > 0

        # Resolve branch 1
        name_1, branch_1 = _resolve_branch_from_db(fork_step.step_id, pstat.process_id, 1)
        assert name_1 == "Resolve group"
        assert len(branch_1) > 0
```

- [ ] **Step 15: Run test to verify it passes**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_resolve_branch_from_db_finds_correct_branch -v`
Expected: PASS

- [ ] **Step 16: Run full Celery integration test suite**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py -v`
Expected: All tests pass.

- [ ] **Step 17: Commit**

```bash
git add test/integration_tests/test_parallel_celery_integration.py
git commit -m "Add Celery integration tests for parallel branch execution"
```

---

## Task 5: Verify Full Test Suite and Fix Any Issues

Run the complete parallel test suite and fix any failures or warnings.

**Files:**
- All parallel test files

- [ ] **Step 1: Run all parallel unit tests**

Run: `uv run pytest test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_join.py test/unit_tests/test_parallel_celery.py test/unit_tests/test_parallel_db.py -v --tb=short 2>&1 | tail -20`
Expected: All tests pass.

- [ ] **Step 2: Run all parallel integration tests**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py -v --tb=short 2>&1 | tail -20`
Expected: All tests pass.

- [ ] **Step 3: Run mypy on changed files**

Run: `uv run mypy orchestrator/services/parallel.py orchestrator/workflow.py orchestrator/db/models.py --no-error-summary 2>&1 | tail -20`
Expected: No new type errors.

- [ ] **Step 4: Run ruff on changed files**

Run: `uv run ruff check orchestrator/services/parallel.py orchestrator/workflow.py test/unit_tests/test_parallel_*.py test/integration_tests/test_parallel_*.py`
Expected: No lint errors.

- [ ] **Step 5: Fix any issues found in steps 1-4**

Address all test failures, type errors, and lint issues. Run the failing command again after each fix to confirm.

- [ ] **Step 6: Run the full test suite one more time**

Run: `uv run pytest test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_join.py test/unit_tests/test_parallel_celery.py test/unit_tests/test_parallel_db.py test/integration_tests/test_parallel_celery_integration.py -v -q --tb=short 2>&1 | tail -10`
Expected: All tests pass, zero warnings.

- [ ] **Step 7: Commit any fixes**

```bash
git add -u
git commit -m "Fix issues found during full parallel test suite verification"
```

---

## Task 6: Run Pre-commit and Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run pre-commit on all changed files**

Run: `pre-commit run --all-files 2>&1 | tail -20`
Expected: All hooks pass.

- [ ] **Step 2: Fix any pre-commit failures and re-run**

Fix formatting/lint issues and run again until all hooks pass.

- [ ] **Step 3: Commit any formatting fixes**

```bash
git add -u
git commit -m "Fix formatting from pre-commit hooks"
```

- [ ] **Step 4: Review the full diff against main**

Run: `git diff main..HEAD --stat` to see all changed files.
Run: `git log --oneline main..HEAD` to see all commits.

Verify the branch is clean and ready for PR.

---

## Test Coverage Summary

After completing this plan, the parallel execution test coverage will be:

| Area | Before | After |
|------|--------|-------|
| Unit: workflow DSL & execution | 37 tests | 37 tests (warnings fixed) |
| Unit: join logic | 18 tests | 18 tests |
| Unit: Celery mocks | 7 tests | 7 tests |
| DB integration: persistence | 3 tests | 11 tests (+8) |
| Celery integration: real execution | 0 tests | 7+ tests (+7) |
| **Total** | **65 tests** | **80+ tests** |

New coverage areas:
- Fork step status/state after success and failure
- Association proxy (child_steps) access
- Multi-step branch relation ordering
- Failed branch persistence
- foreach_parallel DB persistence
- Pipe operator DB persistence
- Cascade delete behavior
- Atomic increment with real DB
- Branch result collection from real DB
- run_celery_branch end-to-end with real DB
- Multi-step Celery branch execution
- Failing Celery branch counter behavior
- Branch resolution from DB metadata
- foreach_parallel Celery dispatch

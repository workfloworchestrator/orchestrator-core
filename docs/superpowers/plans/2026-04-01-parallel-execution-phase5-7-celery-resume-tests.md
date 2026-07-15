# Parallel Execution Phases 5-7: Celery Branch-as-Task, Resume, Tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Celery-based distributed execution of parallel branches, resume/retry support via DB queries, and integration tests for the full parallel execution pipeline.

**Architecture:** Each parallel branch becomes an independent Celery task. A fork step tracks branch count; an atomic `UPDATE...RETURNING` counter detects the last finisher, which collects results from DB, joins them, and resumes the parent workflow. Resume/retry re-executes only failed branches.

**Tech Stack:** Celery, SQLAlchemy (`UPDATE...RETURNING`), pytest, `@pytest.mark.celery`

**Design doc:** `docs/designs/parallel-workflow-execution.md` — sections 4.3 (Celery path), 5 (Phases 5-7)

**Depends on:** Phase 1-4 commit `a1c73323` on branch `parallel-step-design`

---

## File Structure

| File | Role |
|------|------|
| `orchestrator/services/tasks.py` | Add `EXECUTE_PARALLEL_BRANCH` task constant and Celery task registration |
| `orchestrator/services/parallel.py` | **New** — Celery branch execution: `execute_parallel_branch()`, `_atomic_increment_completed()`, `_celery_join_and_resume()` |
| `orchestrator/workflow.py` | Add `_exec_parallel_branches_celery()`, executor dispatch in `_exec_parallel_branches()`, `reconstruct_branch()` |
| `orchestrator/settings.py` | Already has `PARALLEL_BRANCH_QUEUE` (Phase 4) — no changes |
| `test/unit_tests/test_parallel_celery.py` | **New** — Unit tests for atomic counter, branch reconstruction, executor dispatch |
| `test/integration_tests/test_parallel_db.py` | **New** — Integration tests for fork step persistence, branch step relations |

---

### Task 1: Add `EXECUTE_PARALLEL_BRANCH` task constant and queue routing

**Files:**
- Modify: `orchestrator/services/tasks.py:35-64`

- [ ] **Step 1: Add the task constant**

After line 38 (`RESUME_WORKFLOW`), add:

```python
EXECUTE_PARALLEL_BRANCH = "tasks.execute_parallel_branch"
```

- [ ] **Step 2: Add queue routing for the new task**

In `initialise_celery()`, update `celery.conf.task_routes` (line 59-64):

```python
    from orchestrator.settings import app_settings

    parallel_queue = app_settings.PARALLEL_BRANCH_QUEUE or "new_tasks"
    celery.conf.task_routes = {
        NEW_TASK: {"queue": "new_tasks"},
        NEW_WORKFLOW: {"queue": "new_workflows"},
        RESUME_TASK: {"queue": "resume_tasks"},
        RESUME_WORKFLOW: {"queue": "resume_workflows"},
        EXECUTE_PARALLEL_BRANCH: {"queue": parallel_queue},
    }
```

- [ ] **Step 3: Register the Celery task inside `initialise_celery()`**

After the `resume_workflow` task definition (line ~114), add:

```python
    @celery_task(name=EXECUTE_PARALLEL_BRANCH)  # type: ignore
    def execute_parallel_branch(
        process_id: UUID,
        workflow_key: str,
        parallel_group_name: str,
        branch_index: int,
        fork_step_id: UUID,
        initial_state: dict,
        user: str,
    ) -> UUID | None:
        local_logger.info(
            "Execute parallel branch",
            process_id=process_id,
            parallel_group=parallel_group_name,
            branch_index=branch_index,
        )
        try:
            from orchestrator.services.parallel import run_celery_branch

            run_celery_branch(
                process_id=process_id,
                workflow_key=workflow_key,
                parallel_group_name=parallel_group_name,
                branch_index=branch_index,
                fork_step_id=fork_step_id,
                initial_state=initial_state,
                user=user,
            )
        except Exception as exc:
            local_logger.error(
                "Parallel branch failed",
                process_id=process_id,
                branch_index=branch_index,
                details=str(exc),
            )
            return None
        else:
            return process_id
```

- [ ] **Step 4: Run lint**

Run: `uv run ruff check orchestrator/services/tasks.py`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/services/tasks.py
git commit -m "Add EXECUTE_PARALLEL_BRANCH Celery task and queue routing"
```

---

### Task 2: Add `reconstruct_branch()` to workflow.py

**Files:**
- Modify: `orchestrator/workflow.py`

- [ ] **Step 1: Write the failing test**

Create `test/unit_tests/test_parallel_celery.py`:

```python
"""Unit tests for Celery parallel branch support."""
import pytest

from orchestrator.workflow import begin, parallel, step


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


class TestReconstructBranch:
    def test_reconstruct_branch_returns_step_list(self) -> None:
        from orchestrator.workflow import reconstruct_branch

        par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
        branch = reconstruct_branch(par_step, 0)
        assert len(branch) > 0

    def test_reconstruct_branch_index_out_of_range_raises(self) -> None:
        from orchestrator.workflow import reconstruct_branch

        par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
        with pytest.raises(IndexError):
            reconstruct_branch(par_step, 5)

    def test_reconstruct_branch_non_parallel_step_raises(self) -> None:
        from orchestrator.workflow import reconstruct_branch

        with pytest.raises(ValueError, match="not a parallel step"):
            reconstruct_branch(_step_a, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest test/unit_tests/test_parallel_celery.py::TestReconstructBranch -v`
Expected: FAIL — `reconstruct_branch` not defined.

- [ ] **Step 3: Implement `reconstruct_branch()`**

Add to `orchestrator/workflow.py`, after `_make_parallel_step()`:

```python
def reconstruct_branch(parallel_step: Step, branch_index: int) -> StepList:
    """Reconstruct a branch StepList from a parallel step's metadata.

    Used by Celery workers to re-create the branch for execution.
    """
    branches: list[StepList] | None = getattr(parallel_step, "_parallel_branches", None)
    if branches is None:
        raise ValueError(f"Step '{parallel_step.name}' is not a parallel step")
    return branches[branch_index]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest test/unit_tests/test_parallel_celery.py::TestReconstructBranch -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/workflow.py test/unit_tests/test_parallel_celery.py
git commit -m "Add reconstruct_branch() for Celery branch step reconstruction"
```

---

### Task 3: Create `orchestrator/services/parallel.py` with atomic counter and branch execution

**Files:**
- Create: `orchestrator/services/parallel.py`

- [ ] **Step 1: Write the failing test for `_atomic_increment_completed()`**

Add to `test/unit_tests/test_parallel_celery.py`:

```python
from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestAtomicIncrementCompleted:
    @patch("orchestrator.services.parallel.db")
    def test_returns_new_count(self, mock_db: MagicMock) -> None:
        from orchestrator.services.parallel import _atomic_increment_completed

        fork_step_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        mock_db.session.execute.return_value = mock_result

        count = _atomic_increment_completed(fork_step_id)
        assert count == 3
        mock_db.session.commit.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest test/unit_tests/test_parallel_celery.py::TestAtomicIncrementCompleted -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `orchestrator/services/parallel.py`**

```python
"""Parallel branch execution support for Celery workers.

Handles:
- Executing a single branch in a Celery task
- Atomic join counter (UPDATE...RETURNING)
- Last-finisher detection and parent workflow resumption
"""
from __future__ import annotations

from copy import deepcopy
from uuid import UUID

import structlog
from sqlalchemy import text, update

from orchestrator.db import ProcessStepTable, db
from orchestrator.utils.errors import error_state_to_dict
from orchestrator.workflow import (
    Failed,
    Success,
    _exec_steps,
    _join_results,
    _make_branch_dblogstep,
)
from pydantic_forms.types import State

logger = structlog.get_logger(__name__)


def _atomic_increment_completed(fork_step_id: UUID) -> int:
    """Atomically increment parallel_completed_count and return the new value.

    Uses UPDATE...RETURNING for atomic last-finisher detection.
    """
    stmt = (
        update(ProcessStepTable)
        .where(ProcessStepTable.step_id == fork_step_id)
        .values(parallel_completed_count=ProcessStepTable.parallel_completed_count + 1)
        .returning(ProcessStepTable.parallel_completed_count)
    )
    result = db.session.execute(stmt)
    count = result.scalar_one()
    db.session.commit()
    return count


def _collect_branch_results(fork_step_id: UUID) -> list[tuple[int, dict, str]]:
    """Collect branch results from DB via ProcessStepRelationTable.

    Returns list of (branch_index, state, status) sorted by branch_index.
    """
    from orchestrator.db.models import ProcessStepRelationTable

    relations = (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == fork_step_id)
        .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id.desc())
        .all()
    )

    # Group by branch_index, take the last step per branch (highest order_id)
    seen_branches: dict[int, tuple[dict, str]] = {}
    for rel in relations:
        if rel.branch_index not in seen_branches:
            child = rel.child_step
            seen_branches[rel.branch_index] = (child.state, child.status)

    return [
        (branch_idx, state, status)
        for branch_idx, (state, status) in sorted(seen_branches.items())
    ]


def run_celery_branch(
    *,
    process_id: UUID,
    workflow_key: str,
    parallel_group_name: str,
    branch_index: int,
    fork_step_id: UUID,
    initial_state: dict,
    user: str,
) -> None:
    """Execute a single parallel branch in a Celery worker.

    After execution, atomically increments the completed counter.
    If this is the last branch, collects all results and resumes the parent workflow.
    """
    from orchestrator.services.workflows import get_workflow_by_name
    from orchestrator.workflow import ProcessStatus, _STATUSES, reconstruct_branch

    wf_table = get_workflow_by_name(workflow_key)
    if not wf_table:
        raise ValueError(f"Workflow '{workflow_key}' not found")

    # Find the parallel step in the workflow's step list
    wf = wf_table.workflow_fn
    if wf is None:
        raise ValueError(f"Workflow '{workflow_key}' has no workflow function")

    # Walk the step list to find the parallel step by name
    parallel_step = next(
        (s for s in wf.steps if getattr(s, "_parallel_group_name", None) == parallel_group_name),
        None,
    )
    if parallel_step is None:
        raise ValueError(f"Parallel group '{parallel_group_name}' not found in workflow '{workflow_key}'")

    branch = reconstruct_branch(parallel_step, branch_index)

    # Execute the branch with DB logging
    branch_state = deepcopy(initial_state)
    dblogstep = _make_branch_dblogstep(process_id, fork_step_id, branch_index, user)
    try:
        result = _exec_steps(branch, Success(branch_state), dblogstep)
    except Exception as e:
        logger.error("Celery branch execution failed", branch_index=branch_index, error=str(e))
        result = Failed(error_state_to_dict(e))

    # Atomic increment — detect last finisher
    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is None:
        raise ValueError(f"Fork step {fork_step_id} not found")

    completed = _atomic_increment_completed(fork_step_id)
    total = fork_step.parallel_total_branches

    logger.info(
        "Branch completed",
        branch_index=branch_index,
        completed=completed,
        total=total,
        parallel_group=parallel_group_name,
    )

    if completed >= total:
        _celery_join_and_resume(
            process_id=process_id,
            fork_step_id=fork_step_id,
            initial_state=initial_state,
            user=user,
        )


def _celery_join_and_resume(
    *,
    process_id: UUID,
    fork_step_id: UUID,
    initial_state: dict,
    user: str,
) -> None:
    """Called by the last-finishing branch to join results and resume the parent workflow."""
    from orchestrator.workflow import _STATUSES

    branch_data = _collect_branch_results(fork_step_id)

    # Reconstruct Process objects from DB state + status
    results = []
    for _branch_idx, state, status in branch_data:
        process_cls = _STATUSES.get(status, Success)
        results.append(process_cls(state))

    merged = _join_results(initial_state, results)

    # Update fork step with final status
    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is not None:
        fork_step.status = merged.status
        fork_step.state = merged.unwrap() if merged.issuccess() else initial_state
        db.session.commit()

    # Resume the parent workflow
    from orchestrator.services.processes import _get_process, load_process
    from orchestrator.services.executors.threadpool import thread_resume_process

    process = _get_process(process_id)
    thread_resume_process(process, user=user)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_celery.py::TestAtomicIncrementCompleted -v`
Expected: PASS.

- [ ] **Step 5: Run lint**

Run: `uv run ruff check orchestrator/services/parallel.py`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/services/parallel.py test/unit_tests/test_parallel_celery.py
git commit -m "Add orchestrator/services/parallel.py with atomic counter and branch execution"
```

---

### Task 4: Add `_exec_parallel_branches_celery()` and executor dispatch

**Files:**
- Modify: `orchestrator/workflow.py:660-720`

- [ ] **Step 1: Write the failing test for executor dispatch**

Add to `test/unit_tests/test_parallel_celery.py`:

```python
from unittest.mock import patch


class TestExecutorDispatch:
    @patch("orchestrator.workflow.app_settings")
    @patch("orchestrator.workflow._exec_parallel_branches_celery")
    def test_celery_executor_dispatches_to_celery(
        self, mock_celery_exec: MagicMock, mock_settings: MagicMock
    ) -> None:
        from orchestrator.workflow import _exec_parallel_branches

        mock_settings.EXECUTOR = "celery"
        mock_celery_exec.return_value = MagicMock()

        # Provide minimal args — the celery path is mocked
        _exec_parallel_branches(
            branches=[[], []],
            initial_state={"x": 1},
            dblogstep=lambda s, p: p,
            name="test",
        )
        mock_celery_exec.assert_called_once()

    def test_threadpool_executor_is_default(self) -> None:
        """ThreadPool path runs when EXECUTOR != celery (the existing behavior)."""
        from orchestrator.workflow import Success, _exec_parallel_branches

        result = _exec_parallel_branches(
            branches=[[_step_a], [_step_b]],
            initial_state={},
            dblogstep=lambda s, p: p,
            name="test",
        )
        assert result.issuccess()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest test/unit_tests/test_parallel_celery.py::TestExecutorDispatch -v`
Expected: FAIL — `_exec_parallel_branches_celery` not defined.

- [ ] **Step 3: Add `_exec_parallel_branches_celery()` to `workflow.py`**

Add before `_exec_parallel_branches()`:

```python
def _exec_parallel_branches_celery(
    branches: list[StepList],
    initial_state: State,
    name: str,
    process_id: UUID,
    current_user: str,
    fork_step_id: UUID,
) -> Process:
    """Submit parallel branches as Celery tasks and return Waiting.

    The parent workflow suspends (Waiting). Each branch executes in its own Celery
    task. The last finisher detects completion via atomic counter and resumes
    the parent workflow.
    """
    from orchestrator.services.tasks import EXECUTE_PARALLEL_BRANCH, get_celery_task

    trigger_task = get_celery_task(EXECUTE_PARALLEL_BRANCH)
    pstat = process_stat_var.get(None)
    workflow_key = pstat.workflow.name if pstat else ""

    for idx in range(len(branches)):
        trigger_task.delay(
            process_id,
            workflow_key,
            name,
            idx,
            fork_step_id,
            initial_state,
            current_user,
        )

    return Waiting(initial_state | {"__parallel_waiting": True, "__fork_step_id": str(fork_step_id)})
```

- [ ] **Step 4: Update `_exec_parallel_branches()` with executor dispatch**

Replace the existing `_exec_parallel_branches()` function:

```python
def _exec_parallel_branches(
    branches: list[StepList],
    initial_state: State,
    dblogstep: StepLogFuncInternal,
    name: str,
    max_workers: int | None = None,
) -> Process:
    """Execute branches in parallel — dispatches to ThreadPool or Celery based on EXECUTOR setting."""
    from orchestrator.settings import ExecutorType, app_settings

    pstat = process_stat_var.get(None)
    process_id = pstat.process_id if pstat else None
    current_user = pstat.current_user if pstat else ""

    # Create fork step in DB if we have a process context
    fork_step = None
    parent_step_id = None
    if process_id is not None:
        try:
            fork_step = _create_fork_step(process_id, name, initial_state, len(branches), current_user)
            parent_step_id = fork_step.step_id
        except Exception:
            logger.debug("Could not create fork step, skipping branch DB logging", parallel_group=name)
            db.session.rollback()
            process_id = None

    # Celery path: submit branches as tasks and return Waiting
    if app_settings.EXECUTOR == ExecutorType.WORKER and fork_step is not None and parent_step_id is not None:
        return _exec_parallel_branches_celery(
            branches, initial_state, name, process_id, current_user, parent_step_id
        )

    # ThreadPool path (default)
    workers = max_workers if max_workers is not None else len(branches)
    branch_results: list[Process | None] = [None] * len(branches)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _run_branch,
                branch,
                initial_state,
                process_id=process_id,
                parent_step_id=parent_step_id,
                branch_index=idx,
                current_user=current_user,
            ): idx
            for idx, branch in enumerate(branches)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                branch_results[idx] = future.result()
            except Exception as e:
                logger.error("Parallel branch exception", branch_idx=idx, parallel_group=name)
                branch_results[idx] = Failed(error_state_to_dict(e))

    results: list[Process] = [r for r in branch_results if r is not None]

    parallel_start_time = nowtz().timestamp()
    result = _join_results(initial_state, results)

    if fork_step is not None:
        fork_step.status = result.status
        fork_step.state = result.unwrap() if result.issuccess() else initial_state
        fork_step.parallel_completed_count = len(branches)
        db.session.commit()

    return result.map(lambda s: s | {"__replace_last_state": True, "__last_step_started_at": parallel_start_time})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest test/unit_tests/test_parallel_celery.py test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_join.py -v 2>&1 | tail -20`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/workflow.py test/unit_tests/test_parallel_celery.py
git commit -m "Add Celery executor dispatch for parallel branches"
```

---

### Task 5: Add integration test for fork step and branch step DB persistence

**Files:**
- Create: `test/integration_tests/test_parallel_db.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration tests for parallel step DB persistence.

These tests require a running database (via the test fixtures).
"""
import pytest

from orchestrator.db import ProcessStepTable, db
from orchestrator.db.models import ProcessStepRelationTable
from orchestrator.workflow import (
    Success,
    begin,
    done,
    init,
    parallel,
    step,
    workflow,
)
from test.unit_tests.workflows import assert_complete, run_workflow


@step("Int Branch A")
def int_branch_a() -> dict:
    return {"int_a": "done"}


@step("Int Branch B")
def int_branch_b() -> dict:
    return {"int_b": "done"}


@pytest.mark.workflow
class TestParallelDBPersistence:
    def test_fork_step_created_with_branch_count(self, generic_subscription) -> None:
        wf = workflow("DB Parallel WF")(
            lambda: init >> parallel("DB test group", begin >> int_branch_a, begin >> int_branch_b) >> done
        )

        result, process, step_log = run_workflow("DB Parallel WF", {}, wf)
        assert_complete(result)

        fork_steps = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == process.process_id,
                ProcessStepTable.parallel_total_branches.isnot(None),
            )
            .all()
        )
        assert len(fork_steps) == 1
        assert fork_steps[0].parallel_total_branches == 2
        assert fork_steps[0].parallel_completed_count == 2

    def test_branch_steps_linked_via_relation_table(self, generic_subscription) -> None:
        wf = workflow("DB Relation WF")(
            lambda: init >> parallel("Relation test", begin >> int_branch_a, begin >> int_branch_b) >> done
        )

        result, process, step_log = run_workflow("DB Relation WF", {}, wf)
        assert_complete(result)

        fork_step = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == process.process_id,
                ProcessStepTable.parallel_total_branches.isnot(None),
            )
            .one()
        )

        relations = (
            db.session.query(ProcessStepRelationTable)
            .filter(ProcessStepRelationTable.parent_step_id == fork_step.step_id)
            .order_by(ProcessStepRelationTable.branch_index)
            .all()
        )
        assert len(relations) == 2
        assert relations[0].branch_index == 0
        assert relations[1].branch_index == 1

    def test_branch_step_names_include_branch_index(self, generic_subscription) -> None:
        wf = workflow("DB Names WF")(
            lambda: init >> parallel("Name test", begin >> int_branch_a, begin >> int_branch_b) >> done
        )

        result, process, step_log = run_workflow("DB Names WF", {}, wf)
        assert_complete(result)

        branch_steps = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == process.process_id,
                ProcessStepTable.name.like("[Branch %]%"),
            )
            .order_by(ProcessStepTable.name)
            .all()
        )
        assert len(branch_steps) == 2
        assert "[Branch 0]" in branch_steps[0].name
        assert "[Branch 1]" in branch_steps[1].name
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest test/integration_tests/test_parallel_db.py -v --tb=short`
Expected: All PASS (requires database via test fixtures).

Note: If the test infrastructure doesn't provide `generic_subscription` or `run_workflow` with the right signature, adapt to match existing integration test patterns. Check `test/integration_tests/` for examples.

- [ ] **Step 3: Commit**

```bash
git add test/integration_tests/test_parallel_db.py
git commit -m "Add integration tests for parallel step DB persistence"
```

---

### Task 6: Run full test suite, type check, and lint

**Files:** None (verification only)

- [ ] **Step 1: Run mypy on all modified files**

Run: `uv run mypy orchestrator/workflow.py orchestrator/services/parallel.py orchestrator/services/tasks.py --no-error-summary 2>&1 | head -30`
Expected: No new errors.

- [ ] **Step 2: Run ruff on all modified files**

Run: `uv run ruff check orchestrator/workflow.py orchestrator/services/parallel.py orchestrator/services/tasks.py`
Expected: No errors.

- [ ] **Step 3: Run all unit tests**

Run: `uv run pytest test/unit_tests/ -x -q 2>&1 | tail -10`
Expected: All PASS.

- [ ] **Step 4: Run pre-commit**

Run: `pre-commit run --all-files 2>&1 | tail -20`
Expected: All PASS.

- [ ] **Step 5: Fix any issues and commit**

```bash
git add -A
git commit -m "Fix type errors and lint issues from Phases 5-7"
```

---

### Task 7: Final verification and summary

- [ ] **Step 1: Check git status and log**

Run: `git status && git log --oneline -10`

Expected commits (on top of Phase 1-4):
1. `Add EXECUTE_PARALLEL_BRANCH Celery task and queue routing`
2. `Add reconstruct_branch() for Celery branch step reconstruction`
3. `Add orchestrator/services/parallel.py with atomic counter and branch execution`
4. `Add Celery executor dispatch for parallel branches`
5. `Add integration tests for parallel step DB persistence`
6. (Optional) `Fix type errors and lint issues from Phases 5-7`

---

## What This Plan Does NOT Cover

- Actual Celery worker testing with a running broker (`@pytest.mark.celery` end-to-end) — requires Celery test infrastructure that may need separate setup
- `foreach_parallel` Celery path — can be added as a follow-up using the same pattern
- Nested parallelism — out of scope per design doc
- Progress tracking via WebSocket — uses existing broadcast mechanism, no changes needed
- Documentation updates — can be done as a separate task after code is stable

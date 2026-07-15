# Parallel Step Execution: DB Schema + ThreadPool + Validation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-branch DB logging with `ProcessStepRelationTable`, update ThreadPool execution to use real step logging, and add `callback_step` validation in parallel branches.

**Architecture:** New `ProcessStepRelationTable` links fork (parent) steps to child (branch) steps via association proxy on `ProcessStepTable`. Each parallel branch thread gets its own DB session and writes real step rows. A `process_stat_var` ContextVar provides `process_id` and `current_user` to the parallel execution context.

**Tech Stack:** SQLAlchemy (association_proxy, mapped_column), Alembic migrations, Python threading (ThreadPoolExecutor), ContextVars, pytest

**Design doc:** `docs/designs/parallel-workflow-execution.md` — sections 4.3, 4.8, 5 (Phases 1-4)

---

## File Structure

| File | Role |
|------|------|
| `orchestrator/db/models.py` | Add `ProcessStepRelationTable`, new columns + relationships on `ProcessStepTable` |
| `orchestrator/db/__init__.py` | Export `ProcessStepRelationTable` |
| `orchestrator/migrations/versions/schema/2026-04-01_<hash>_add_process_step_relations.py` | Alembic migration |
| `orchestrator/workflow.py` | `process_stat_var`, `_make_branch_dblogstep`, update `_run_branch`, update `_exec_parallel_branches`, `_is_callback_step` marker, callback validation |
| `orchestrator/settings.py` | Add `PARALLEL_BRANCH_QUEUE` setting |
| `test/unit_tests/test_parallel_join.py` | Unit tests for `_join_results`, `_worst_status`, callback rejection |
| `test/unit_tests/test_parallel_workflow.py` | Update existing tests for DB logging |

---

### Task 1: Add `ProcessStepRelationTable` to DB models

**Files:**
- Modify: `orchestrator/db/models.py:173-187`

- [ ] **Step 1: Write the `ProcessStepRelationTable` class**

Add after `ProcessStepTable` (after line 187):

```python
class ProcessStepRelationTable(BaseModel):
    __tablename__ = "process_step_relations"

    parent_step_id = mapped_column(
        UUIDType,
        ForeignKey("process_steps.stepid", ondelete="CASCADE"),
        primary_key=True,
    )
    child_step_id = mapped_column(
        UUIDType,
        ForeignKey("process_steps.stepid", ondelete="CASCADE"),
        primary_key=True,
    )
    order_id = mapped_column(Integer(), primary_key=True)
    branch_index = mapped_column(Integer(), nullable=False)

    parent_step: Mapped["ProcessStepTable"] = relationship(
        "ProcessStepTable",
        back_populates="child_step_relations",
        foreign_keys=[parent_step_id],
    )
    child_step: Mapped["ProcessStepTable"] = relationship(
        "ProcessStepTable",
        back_populates="parent_step_relations",
        foreign_keys=[child_step_id],
    )
```

- [ ] **Step 2: Add new columns and relationships to `ProcessStepTable`**

Add two nullable columns and relationships to `ProcessStepTable` (at line ~187, after `commit_hash`):

```python
class ProcessStepTable(BaseModel):
    __tablename__ = "process_steps"
    # ... existing columns ...
    commit_hash = mapped_column(String(40), nullable=True, default=GIT_COMMIT_HASH)

    # Parallel join tracking (only set on fork steps)
    parallel_total_branches = mapped_column(Integer(), nullable=True)
    parallel_completed_count = mapped_column(Integer(), nullable=True, server_default=text("0"))

    # Relationships for parallel branch steps
    child_step_relations: Mapped[list["ProcessStepRelationTable"]] = relationship(
        "ProcessStepRelationTable",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="parent_step",
        foreign_keys="[ProcessStepRelationTable.parent_step_id]",
        order_by="ProcessStepRelationTable.order_id",
    )
    parent_step_relations: Mapped[list["ProcessStepRelationTable"]] = relationship(
        "ProcessStepRelationTable",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="child_step",
        foreign_keys="[ProcessStepRelationTable.child_step_id]",
    )

    child_steps = association_proxy("child_step_relations", "child_step")
```

- [ ] **Step 3: Add index on the relation table**

Add after `ProcessStepRelationTable` class:

```python
process_step_relation_index = Index(
    "process_step_relation_p_c_o_ix",
    ProcessStepRelationTable.parent_step_id,
    ProcessStepRelationTable.child_step_id,
    ProcessStepRelationTable.order_id,
    unique=True,
)
```

- [ ] **Step 4: Run type check to verify model definitions**

Run: `uv run mypy orchestrator/db/models.py --no-error-summary 2>&1 | head -30`
Expected: No new errors related to `ProcessStepRelationTable` or `ProcessStepTable` changes.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/db/models.py
git commit -m "Add ProcessStepRelationTable and parallel columns on ProcessStepTable"
```

---

### Task 2: Export new table and update `__init__.py`

**Files:**
- Modify: `orchestrator/db/__init__.py:19-40` (imports) and `77-120` (`__all__` and `ALL_DB_MODELS`)

- [ ] **Step 1: Add import of `ProcessStepRelationTable`**

In `orchestrator/db/__init__.py`, add to the import block (around line 24):

```python
from orchestrator.db.models import (  # noqa: F401
    AgentRunTable,
    EngineSettingsTable,
    FixedInputTable,
    InputStateTable,
    ProcessStepRelationTable,  # ADD THIS
    ProcessStepTable,
    # ... rest unchanged
)
```

- [ ] **Step 2: Add to `__all__` list**

Add `"ProcessStepRelationTable"` to the `__all__` list (after `"ProcessStepTable"`):

```python
__all__ = [
    # ...
    "ProcessStepTable",
    "ProcessStepRelationTable",  # ADD THIS
    # ...
]
```

- [ ] **Step 3: Add to `ALL_DB_MODELS` list**

Add `ProcessStepRelationTable` to the `ALL_DB_MODELS` list (after `ProcessStepTable`):

```python
ALL_DB_MODELS: list[type[DbBaseModel]] = [
    # ...
    ProcessStepTable,
    ProcessStepRelationTable,  # ADD THIS
    # ...
]
```

- [ ] **Step 4: Run lint**

Run: `uv run ruff check orchestrator/db/__init__.py`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/db/__init__.py
git commit -m "Export ProcessStepRelationTable from orchestrator.db"
```

---

### Task 3: Create Alembic migration

**Files:**
- Create: `orchestrator/migrations/versions/schema/2026-04-01_add_process_step_relations.py`

- [ ] **Step 1: Generate migration with alembic**

Run: `cd /Users/boers001/Documents/SURF/projects/orchestrator-core && uv run alembic revision --autogenerate -m "add_process_step_relations"`

This should detect:
1. New `process_step_relations` table
2. New columns `parallel_total_branches` and `parallel_completed_count` on `process_steps`

- [ ] **Step 2: Review and clean up the generated migration**

Open the generated file and verify it contains:

```python
def upgrade() -> None:
    op.add_column("process_steps", sa.Column("parallel_total_branches", sa.Integer(), nullable=True))
    op.add_column("process_steps", sa.Column("parallel_completed_count", sa.Integer(), nullable=True,
                                              server_default=sa.text("0")))
    op.create_table(
        "process_step_relations",
        sa.Column("parent_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("child_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("order_id", sa.Integer(), primary_key=True),
        sa.Column("branch_index", sa.Integer(), nullable=False),
    )
    op.create_index("process_step_relation_p_c_o_ix", "process_step_relations",
                    ["parent_step_id", "child_step_id", "order_id"], unique=True)

def downgrade() -> None:
    op.drop_index("process_step_relation_p_c_o_ix", table_name="process_step_relations")
    op.drop_table("process_step_relations")
    op.drop_column("process_steps", "parallel_completed_count")
    op.drop_column("process_steps", "parallel_total_branches")
```

Remove any auto-detected changes not related to this feature (e.g. vector columns, other schema drift).

- [ ] **Step 3: Commit**

```bash
git add orchestrator/migrations/versions/schema/
git commit -m "Add migration for process_step_relations table and parallel columns"
```

---

### Task 4: Add `PARALLEL_BRANCH_QUEUE` setting

**Files:**
- Modify: `orchestrator/settings.py:62`

- [ ] **Step 1: Add the setting**

Add after `EXECUTOR` (line 62) in `AppSettings`:

```python
    EXECUTOR: str = ExecutorType.THREADPOOL
    PARALLEL_BRANCH_QUEUE: str = ""  # empty = use default workflow/tasks queue
```

- [ ] **Step 2: Run type check**

Run: `uv run mypy orchestrator/settings.py --no-error-summary`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add orchestrator/settings.py
git commit -m "Add PARALLEL_BRANCH_QUEUE setting for parallel branch Celery queue"
```

---

### Task 5: Add `process_stat_var` ContextVar and set it in `runwf`

**Files:**
- Modify: `orchestrator/workflow.py:74` (after `step_log_fn_var`) and `orchestrator/workflow.py:1899-1927` (`runwf`)

- [ ] **Step 1: Add the ContextVar**

After `step_log_fn_var` (line 74):

```python
step_log_fn_var: contextvars.ContextVar[StepLogFuncInternal] = contextvars.ContextVar("log_step_fn")
process_stat_var: contextvars.ContextVar["ProcessStat"] = contextvars.ContextVar("process_stat")
```

- [ ] **Step 2: Set the ContextVar in `runwf`**

In `runwf` (around line 1923), add `process_stat_var.set(pstat)` alongside the existing `step_log_fn_var.set`:

```python
    step_log_fn_var.set(_logstep)
    process_stat_var.set(pstat)
    executed_steps = _exec_steps(steps, next_state, _logstep)
```

- [ ] **Step 3: Run type check**

Run: `uv run mypy orchestrator/workflow.py --no-error-summary 2>&1 | head -20`
Expected: No new errors.

- [ ] **Step 4: Commit**

```bash
git add orchestrator/workflow.py
git commit -m "Add process_stat_var ContextVar for parallel execution context"
```

---

### Task 6: Add `_make_branch_dblogstep` and update `_run_branch`

**Files:**
- Modify: `orchestrator/workflow.py:557-580` (replace `_noop_dblogstep` and update `_run_branch`)

- [ ] **Step 1: Write the failing test**

Create `test/unit_tests/test_parallel_join.py` with the `TestJoinResults` tests from design doc section 6.2. These test the existing `_join_results` function which doesn't change, but establishes a baseline:

```python
"""Unit tests for parallel join logic: _join_results, _worst_status."""
import pytest

from orchestrator.workflow import (
    AwaitingCallback,
    Failed,
    Success,
    Suspend,
    Waiting,
    _join_results as join_results,
    _worst_status as worst_status,
)


class TestWorstStatus:
    @pytest.mark.parametrize(
        "results, expected_check",
        [
            ([Failed({"error": "boom"})], "isfailed"),
            ([Waiting({"w": 1})], "iswaiting"),
            ([Suspend({"s": 1})], "issuspend"),
            ([AwaitingCallback({"ac": 1})], "isawaitingcallback"),
            ([Success({"a": 1}), Success({"b": 2})], None),
            ([Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
            ([Suspend({"s": 1}), Failed({"error": "x"})], "isfailed"),
            ([AwaitingCallback({"ac": 1}), Failed({"error": "x"})], "isfailed"),
            ([Suspend({"s": 1}), Waiting({"w": 1})], "iswaiting"),
            ([AwaitingCallback({"ac": 1}), Waiting({"w": 1})], "iswaiting"),
            ([AwaitingCallback({"ac": 1}), Suspend({"s": 1})], "issuspend"),
            ([Success({"a": 1}), Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
            ([Success({"a": 1}), Suspend({"s": 1}), AwaitingCallback({"ac": 1})], "issuspend"),
        ],
        ids=[
            "single-failed",
            "single-waiting",
            "single-suspend",
            "single-awaiting-callback",
            "all-success",
            "waiting-and-failed",
            "suspend-and-failed",
            "awaiting-callback-and-failed",
            "suspend-and-waiting",
            "awaiting-callback-and-waiting",
            "awaiting-callback-and-suspend",
            "three-branches-failed-wins",
            "three-branches-suspend-wins",
        ],
    )
    def test_worst_status_priority(self, results, expected_check):
        fallback = Success({})
        worst = worst_status(results, fallback)
        if expected_check is None:
            assert worst is None
        else:
            assert worst is not None
            assert getattr(worst, expected_check)()


class TestJoinResults:
    def test_merge_disjoint_keys(self):
        initial = {"x": 0}
        results = [Success({"x": 0, "a": 1}), Success({"x": 0, "b": 2})]
        merged = join_results(initial, results)
        assert merged.issuccess()
        state = merged.unwrap()
        assert state["a"] == 1
        assert state["b"] == 2

    def test_key_conflict_raises_value_error(self):
        initial = {"x": 0}
        results = [
            Success({"x": 0, "conflict_key": "from_a"}),
            Success({"x": 0, "conflict_key": "from_b"}),
        ]
        with pytest.raises(ValueError, match="key conflict"):
            join_results(initial, results)

    def test_dunder_keys_excluded_from_conflict_detection(self):
        initial = {}
        results = [
            Success({"__internal": "val_a", "a": 1}),
            Success({"__internal": "val_b", "b": 2}),
        ]
        merged = join_results(initial, results)
        assert merged.issuccess()

    def test_empty_branch_results(self):
        initial = {"x": 1}
        result = join_results(initial, [])
        assert result.issuccess()
        assert result.unwrap()["x"] == 1

    @pytest.mark.parametrize(
        "branch_results, expected_check",
        [
            ([Failed({"error": "boom"}), Success({"a": 1})], "isfailed"),
            ([Success({"a": 1}), Waiting({"w": 1})], "iswaiting"),
            ([Suspend({"s": 1}), Success({"a": 1})], "issuspend"),
        ],
        ids=["failed-beats-success", "waiting-beats-success", "suspend-beats-success"],
    )
    def test_non_success_propagated(self, branch_results, expected_check):
        initial = {}
        result = join_results(initial, branch_results)
        assert getattr(result, expected_check)()
```

- [ ] **Step 2: Run tests to verify they pass (baseline)**

Run: `uv run pytest test/unit_tests/test_parallel_join.py -v`
Expected: All PASS (these test existing functions).

- [ ] **Step 3: Replace `_noop_dblogstep` with `_make_branch_dblogstep`**

Replace `_noop_dblogstep` (lines 557-563) in `orchestrator/workflow.py`:

```python
def _make_branch_dblogstep(
    process_id: UUID,
    parent_step_id: UUID,
    branch_index: int,
    current_user: str,
) -> StepLogFuncInternal:
    """Create a step logger for a parallel branch that writes its own ProcessStepTable rows.

    Each branch step is persisted individually and linked to the parent fork step
    via ProcessStepRelationTable.
    """
    import itertools

    from orchestrator.db.models import ProcessStepRelationTable

    order_counter = itertools.count()

    def branch_dblogstep(step_: Step, p: Process) -> Process:
        step_state = p.unwrap()
        step_name = step_state.pop("__step_name_override", step_.name)

        child_step = ProcessStepTable(
            process_id=process_id,
            name=f"[Branch {branch_index}] {step_name}",
            status=p.status,
            state=step_state,
            created_by=current_user,
        )
        db.session.add(child_step)
        db.session.flush()  # get step_id assigned

        relation = ProcessStepRelationTable(
            parent_step_id=parent_step_id,
            child_step_id=child_step.step_id,
            order_id=next(order_counter),
            branch_index=branch_index,
        )
        db.session.add(relation)
        db.session.commit()
        return p.__class__(child_step.state)

    return branch_dblogstep
```

- [ ] **Step 4: Update `_run_branch` to accept DB logging parameters**

Replace `_run_branch` (lines 566-580):

```python
def _run_branch(
    branch: StepList,
    initial_state: State,
    *,
    process_id: UUID | None = None,
    parent_step_id: UUID | None = None,
    branch_index: int = 0,
    current_user: str = "",
    state_seed: State | None = None,
) -> Process:
    """Execute a single parallel branch in its own database scope.

    Args:
        branch: The step list to execute.
        initial_state: The base state to deep-copy for this branch.
        process_id: Process ID for DB logging (None = no DB logging).
        parent_step_id: Fork step ID to link child steps to.
        branch_index: Index of this branch (0-based).
        current_user: User who started the workflow.
        state_seed: Optional per-branch state overrides (used by foreach_parallel).
    """
    with db.database_scope():
        branch_state = deepcopy(initial_state)
        if state_seed is not None:
            branch_state.update(state_seed)

        if process_id is not None and parent_step_id is not None:
            dblogstep = _make_branch_dblogstep(process_id, parent_step_id, branch_index, current_user)
        else:
            dblogstep = lambda step_, p: p  # no-op fallback

        return _exec_steps(branch, Success(branch_state), dblogstep)
```

- [ ] **Step 5: Run existing parallel tests**

Run: `uv run pytest test/unit_tests/test_parallel_workflow.py -v 2>&1 | tail -20`
Expected: All existing tests still PASS (they don't use DB, so `process_id=None` hits the no-op fallback).

- [ ] **Step 6: Commit**

```bash
git add orchestrator/workflow.py test/unit_tests/test_parallel_join.py
git commit -m "Add _make_branch_dblogstep and update _run_branch for per-branch DB logging"
```

---

### Task 7: Update `_exec_parallel_branches` to create fork step and pass DB context

**Files:**
- Modify: `orchestrator/workflow.py:583-613` (`_exec_parallel_branches`)

- [ ] **Step 1: Add `_create_fork_step` helper**

Add before `_exec_parallel_branches`:

```python
def _create_fork_step(
    process_id: UUID,
    name: str,
    initial_state: State,
    total_branches: int,
    current_user: str,
) -> ProcessStepTable:
    """Create a fork step in the DB that tracks the parallel group."""
    fork_step = ProcessStepTable(
        process_id=process_id,
        name=name,
        status=StepStatus.SUCCESS,
        state=initial_state,
        created_by=current_user,
        parallel_total_branches=total_branches,
        parallel_completed_count=0,
    )
    db.session.add(fork_step)
    db.session.flush()  # get step_id assigned
    db.session.commit()
    return fork_step
```

- [ ] **Step 2: Update `_exec_parallel_branches` to use fork step and branch logging**

Replace `_exec_parallel_branches` (lines 583-613):

```python
def _exec_parallel_branches(
    branches: list[StepList],
    initial_state: State,
    dblogstep: StepLogFuncInternal,
    name: str,
    max_workers: int | None = None,
) -> Process:
    """Execute branches in parallel using ThreadPoolExecutor, each with an isolated state copy."""
    workers = max_workers if max_workers is not None else len(branches)

    # Get process context from ContextVar (set in runwf)
    pstat = process_stat_var.get(None)
    process_id = pstat.process_id if pstat else None
    current_user = pstat.current_user if pstat else ""

    # Create fork step in DB if we have a process context
    fork_step = None
    parent_step_id = None
    if process_id is not None:
        fork_step = _create_fork_step(process_id, name, initial_state, len(branches), current_user)
        parent_step_id = fork_step.step_id

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

    # Update fork step with final status
    if fork_step is not None:
        fork_step.status = result.status
        fork_step.state = result.unwrap() if result.issuccess() else initial_state
        fork_step.parallel_completed_count = len(branches)
        db.session.commit()

    return result.map(lambda s: s | {"__replace_last_state": True, "__last_step_started_at": parallel_start_time})
```

- [ ] **Step 3: Update `foreach_parallel` to pass DB context to `_run_branch`**

In `foreach_parallel` (around line 759), update the `executor.submit` call:

```python
        # Get process context
        pstat = process_stat_var.get(None)
        process_id = pstat.process_id if pstat else None
        current_user = pstat.current_user if pstat else ""

        fork_step = None
        parent_step_id = None
        if process_id is not None:
            fork_step = _create_fork_step(process_id, name, initial_state, len(items), current_user)
            parent_step_id = fork_step.step_id

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
                    state_seed=seed,
                ): idx
                for idx, seed in enumerate(seeds)
            }
```

And after the join, update the fork step:

```python
        if fork_step is not None:
            fork_step.status = result.status if not result.isfailed() else StepStatus.FAILED
            fork_step.state = result.unwrap() if result.issuccess() else initial_state
            fork_step.parallel_completed_count = len(items)
            db.session.commit()
```

- [ ] **Step 4: Run existing parallel tests**

Run: `uv run pytest test/unit_tests/test_parallel_workflow.py -v 2>&1 | tail -20`
Expected: All PASS. Unit tests don't have a DB, so `process_stat_var.get(None)` returns None and the fork step creation is skipped.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/workflow.py
git commit -m "Update _exec_parallel_branches and foreach_parallel with fork step and DB logging"
```

---

### Task 8: Add `_is_callback_step` marker and validation

**Files:**
- Modify: `orchestrator/workflow.py:804-827` (`callback_step`) and `orchestrator/workflow.py:616-644` (`_make_parallel_step`)

- [ ] **Step 1: Write the failing test for callback rejection**

Add to `test/unit_tests/test_parallel_join.py`:

```python
from orchestrator.workflow import begin, callback_step, parallel, step


@step("CB Action")
def _cb_action():
    return {}


@step("CB Validate")
def _cb_validate():
    return {}


_test_callback = callback_step("Test callback", _cb_action, _cb_validate)


class TestCallbackStepRejection:
    def test_callback_step_in_parallel_raises(self):
        @step("Branch A")
        def branch_a():
            return {"a": 1}

        with pytest.raises(ValueError, match="callback"):
            parallel("Invalid parallel", begin >> branch_a, begin >> _test_callback)

    def test_callback_step_via_pipe_raises(self):
        @step("Branch A")
        def branch_a():
            return {"a": 1}

        with pytest.raises(ValueError, match="callback"):
            begin >> ((begin >> branch_a) | (begin >> _test_callback))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest test/unit_tests/test_parallel_join.py::TestCallbackStepRejection -v`
Expected: FAIL — callback_step is not yet rejected.

- [ ] **Step 3: Add `_is_callback_step` marker to `callback_step()` return value**

In `callback_step()` (around line 825-827), add the marker before returning:

```python
def callback_step(
    name: str,
    action_step: Step,
    validate_step: Step,
    result_key: str | None = None,
    callback_route_key: str = DEFAULT_CALLBACK_ROUTE_KEY,
) -> Step:
    # ... existing code ...
    create_endpoint_step = step(f"{name} - Create endpoint")(_create_endpoint_step(key=callback_route_key))
    await_step = _awaitstep(f"{name} - Await callback", result_key=result_key)
    cleanup_step = step(f"{name} - Cleanup callback step")(lambda: {"__remove_keys": [CALLBACK_TOKEN_KEY]})
    result = step_group(
        name=name, steps=begin >> create_endpoint_step >> action_step >> await_step >> validate_step >> cleanup_step
    )
    result._is_callback_step = True  # type: ignore[attr-defined]
    return result
```

- [ ] **Step 4: Add callback validation in `_make_parallel_step`**

In `_make_parallel_step` (around line 627-633), after the existing inputstep check, add:

```python
    for branch_idx, branch in enumerate(branches):
        for s in branch:
            if s.form is not None:
                raise ValueError(
                    f"Parallel branches must not contain inputsteps. "
                    f"Found inputstep '{s.name}' in branch {branch_idx}."
                )
            if getattr(s, "_is_callback_step", False):
                raise ValueError(
                    f"Parallel branches must not contain callback steps. "
                    f"Found callback_step '{s.name}' in branch {branch_idx}."
                )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest test/unit_tests/test_parallel_join.py -v`
Expected: All PASS including the two new callback rejection tests.

- [ ] **Step 6: Run ALL parallel tests to check for regressions**

Run: `uv run pytest test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_join.py -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add orchestrator/workflow.py test/unit_tests/test_parallel_join.py
git commit -m "Add callback_step rejection in parallel branches"
```

---

### Task 9: Add `_parallel_branches` and `_parallel_group_name` metadata to parallel steps

**Files:**
- Modify: `orchestrator/workflow.py:616-644` (`_make_parallel_step`)

- [ ] **Step 1: Add metadata attributes at the end of `_make_parallel_step`**

At the end of `_make_parallel_step`, before `return`:

```python
    step_fn = make_step_function(func, name, retry_auth_callback=retry_auth_callback)
    # Attach metadata for Celery step reconstruction (Phase 5)
    step_fn._parallel_branches = branches  # type: ignore[attr-defined]
    step_fn._parallel_group_name = name  # type: ignore[attr-defined]
    return step_fn
```

This replaces the existing `return make_step_function(...)` line.

- [ ] **Step 2: Run tests**

Run: `uv run pytest test/unit_tests/test_parallel_workflow.py -v 2>&1 | tail -10`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add orchestrator/workflow.py
git commit -m "Attach parallel branch metadata to step for Celery reconstruction"
```

---

### Task 10: Run full test suite and type checks

**Files:** None (verification only)

- [ ] **Step 1: Run type checker**

Run: `uv run mypy orchestrator/workflow.py orchestrator/db/models.py orchestrator/settings.py --no-error-summary 2>&1 | head -30`
Expected: No new errors.

- [ ] **Step 2: Run linter**

Run: `uv run ruff check orchestrator/workflow.py orchestrator/db/models.py orchestrator/db/__init__.py orchestrator/settings.py`
Expected: No errors.

- [ ] **Step 3: Run all unit tests**

Run: `uv run pytest test/unit_tests/ -x -q 2>&1 | tail -20`
Expected: All PASS.

- [ ] **Step 4: Run pre-commit**

Run: `pre-commit run --all-files 2>&1 | tail -20`
Expected: All PASS.

---

### Task 11: Final commit and summary

- [ ] **Step 1: Check git status**

Run: `git status && git log --oneline -10`

Verify all changes are committed. Expected commits:
1. `Add ProcessStepRelationTable and parallel columns on ProcessStepTable`
2. `Export ProcessStepRelationTable from orchestrator.db`
3. `Add migration for process_step_relations table and parallel columns`
4. `Add PARALLEL_BRANCH_QUEUE setting for parallel branch Celery queue`
5. `Add process_stat_var ContextVar for parallel execution context`
6. `Add _make_branch_dblogstep and update _run_branch for per-branch DB logging`
7. `Update _exec_parallel_branches and foreach_parallel with fork step and DB logging`
8. `Add callback_step rejection in parallel branches`
9. `Attach parallel branch metadata to step for Celery reconstruction`

---

## What This Plan Does NOT Cover (Phase 5-7, separate plan)

- Celery branch-as-task execution (`_exec_parallel_branches_celery`)
- Atomic join counter (`_atomic_increment_completed`)
- Last-finisher continuation (`_celery_join_and_resume`)
- Executor dispatch (`match app_settings.EXECUTOR`)
- Resume/retry via DB queries (partial retry)
- Integration tests with real DB
- Celery integration tests

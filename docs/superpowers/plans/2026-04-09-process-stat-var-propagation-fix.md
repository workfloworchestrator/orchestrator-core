# Fix ContextVar Propagation for Nested Parallel Execution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `process_stat_var` propagation so nested parallel steps (threadpool and Celery paths) create fork steps and branch relations in the DB.

**Architecture:** Three changes: (1) wrap `executor.submit()` with `copy_context().run()` for threadpool propagation, (2) set `process_stat_var` in `run_worker_branch` for Celery workers, (3) add recursive `_find_parallel_step` to search nested step trees in `_resolve_branch_from_db`.

**Tech Stack:** Python 3.11+, contextvars, SQLAlchemy, Celery (optional)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `orchestrator/workflow.py` | Add `copy_context` wrapper in `_run_threadpool_branches` |
| `orchestrator/services/parallel.py` | Add `_find_parallel_step` recursive helper; update `_resolve_branch_from_db`; set `process_stat_var` in `run_worker_branch` |
| `test/unit_tests/test_parallel_stress.py` | Update nested parallel test assertions (fork step counts), add `_find_parallel_step` unit tests |

---

### Task 1: Threadpool path — wrap `executor.submit` with `copy_context().run()`

**Files:**
- Modify: `orchestrator/workflow.py:694-706`
- Test: `test/unit_tests/test_parallel_stress.py`

- [ ] **Step 1: Write a failing test that proves inner fork steps are now created**

Add this test to `test/unit_tests/test_parallel_stress.py` after the existing `test_two_level_nested_parallel`:

```python
@pytest.mark.workflow
def test_nested_parallel_creates_inner_fork_step() -> None:
    """After copy_context fix, nested parallel creates fork steps at BOTH levels.

    Structure:
        init >> parallel("Outer",
            begin >> outer_a >> parallel("Inner", begin >> inner_x, begin >> inner_y),
            begin >> outer_b,
        ) >> done

    Verifies:
    - 2 fork steps in DB (Outer + Inner)
    - Inner fork step has parallel_total_branches=2
    - Inner fork step has parallel_completed_count=2
    - Inner fork step has branch relations with indices {0, 1}
    """

    @workflow()
    def nested_inner_fork_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> outer_a >> parallel("Inner", begin >> inner_x, begin >> inner_y),
                begin >> outer_b,
            )
            >> done
        )

    with WorkflowInstanceForTests(nested_inner_fork_wf, "nested_inner_fork_wf"):
        result, pstat, _step_log = run_workflow("nested_inner_fork_wf", [{}])
        assert_complete(result)

        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 2, f"Expected 2 fork steps (Outer + Inner), got {len(fork_steps)}"

        fork_by_name = {fs.name: fs for fs in fork_steps}
        assert set(fork_by_name.keys()) == {"Outer", "Inner"}

        inner_fork = fork_by_name["Inner"]
        assert inner_fork.parallel_total_branches == 2
        assert inner_fork.parallel_completed_count == 2

        inner_relations = _get_relations(inner_fork.step_id)
        inner_branch_indices = {rel.branch_index for rel in inner_relations}
        assert inner_branch_indices == {0, 1}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py::test_nested_parallel_creates_inner_fork_step -v`
Expected: FAIL with `AssertionError: Expected 2 fork steps (Outer + Inner), got 1`

- [ ] **Step 3: Add `copy_context` import and wrap `executor.submit`**

In `orchestrator/workflow.py`, add the `copy_context` import at line 17 (existing `contextvars` import):

```python
from contextvars import copy_context
```

Then modify `_run_threadpool_branches` (lines 694-706) — wrap each `executor.submit` call:

```python
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                copy_context().run,
                _run_branch,
                branches[idx] if len(branches) > 1 else branches[0],
                initial_state,
                process_id=process_id,
                parent_step_id=fork_step_id,
                branch_index=idx,
                current_user=current_user,
                state_seed=seeds[idx] if seeds else None,
            ): idx
            for idx in range(n_branches)
        }
```

The key change is: `executor.submit(copy_context().run, _run_branch, ...)` instead of `executor.submit(_run_branch, ...)`. Each `copy_context()` call creates a snapshot of the current thread's ContextVars (including `process_stat_var` and `step_log_fn_var`). The `.run()` method executes `_run_branch` inside that copied context.

- [ ] **Step 4: Run the new test to verify it passes**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py::test_nested_parallel_creates_inner_fork_step -v`
Expected: PASS

- [ ] **Step 5: Run all existing parallel tests to check for regressions**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_db.py -v`
Expected: All pass (some stress tests may need assertion updates — see Task 4)

- [ ] **Step 6: Commit**

```bash
git add orchestrator/workflow.py test/unit_tests/test_parallel_stress.py
git commit -m "Propagate ContextVars to threadpool branches via copy_context"
```

---

### Task 2: Celery worker path — recursive `_find_parallel_step` and `process_stat_var` setup

**Files:**
- Modify: `orchestrator/services/parallel.py:82-116` (recursive search), `orchestrator/services/parallel.py:119-160` (set process_stat_var)
- Test: `test/unit_tests/test_parallel_stress.py`

- [ ] **Step 1: Write a unit test for the `_find_parallel_step` recursive helper**

Add to `test/unit_tests/test_parallel_stress.py`:

```python
from orchestrator.services.parallel import _find_parallel_step


@pytest.mark.workflow
def test_find_parallel_step_top_level() -> None:
    """_find_parallel_step finds a parallel step at the top level of wf.steps."""

    @workflow()
    def flat_wf():
        return init >> parallel("TopLevel", begin >> outer_a, begin >> outer_b) >> done

    with WorkflowInstanceForTests(flat_wf, "flat_wf"):
        from orchestrator.workflows import get_workflow

        wf = get_workflow("flat_wf")
        result = _find_parallel_step(wf.steps, "TopLevel")
        assert result is not None
        assert getattr(result, "_parallel_group_name", None) == "TopLevel"


@pytest.mark.workflow
def test_find_parallel_step_nested_in_parallel_branch() -> None:
    """_find_parallel_step finds a parallel step nested inside another parallel step's branch."""

    @workflow()
    def nested_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> outer_a >> parallel("Inner", begin >> inner_x, begin >> inner_y),
                begin >> outer_b,
            )
            >> done
        )

    with WorkflowInstanceForTests(nested_wf, "nested_find_wf"):
        from orchestrator.workflows import get_workflow

        wf = get_workflow("nested_find_wf")
        result = _find_parallel_step(wf.steps, "Inner")
        assert result is not None
        assert getattr(result, "_parallel_group_name", None) == "Inner"


@pytest.mark.workflow
def test_find_parallel_step_nested_in_foreach_template() -> None:
    """_find_parallel_step finds a parallel step nested inside a foreach_parallel template."""

    @workflow()
    def fe_nested_wf():
        return (
            init
            >> foreach_parallel(
                "FEOuter",
                "items",
                begin >> parallel("InsideFE", begin >> inner_x, begin >> inner_y),
            )
            >> done
        )

    with WorkflowInstanceForTests(fe_nested_wf, "fe_nested_find_wf"):
        from orchestrator.workflows import get_workflow

        wf = get_workflow("fe_nested_find_wf")
        result = _find_parallel_step(wf.steps, "InsideFE")
        assert result is not None
        assert getattr(result, "_parallel_group_name", None) == "InsideFE"


@pytest.mark.workflow
def test_find_parallel_step_three_levels_deep() -> None:
    """_find_parallel_step finds a step 3 levels deep."""

    @workflow()
    def deep_wf():
        return (
            init
            >> parallel(
                "L1",
                begin >> parallel("L2", begin >> parallel("L3", begin >> deep_p, begin >> deep_q), begin >> mid_m),
                begin >> top_c,
            )
            >> done
        )

    with WorkflowInstanceForTests(deep_wf, "deep_find_wf"):
        from orchestrator.workflows import get_workflow

        wf = get_workflow("deep_find_wf")

        for name in ("L1", "L2", "L3"):
            result = _find_parallel_step(wf.steps, name)
            assert result is not None, f"Could not find parallel step '{name}'"
            assert getattr(result, "_parallel_group_name", None) == name


@pytest.mark.workflow
def test_find_parallel_step_returns_none_for_missing() -> None:
    """_find_parallel_step returns None when group name doesn't exist."""

    @workflow()
    def simple_wf():
        return init >> parallel("Exists", begin >> outer_a, begin >> outer_b) >> done

    with WorkflowInstanceForTests(simple_wf, "missing_find_wf"):
        from orchestrator.workflows import get_workflow

        wf = get_workflow("missing_find_wf")
        result = _find_parallel_step(wf.steps, "DoesNotExist")
        assert result is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py -k "test_find_parallel_step" -v`
Expected: FAIL with `ImportError: cannot import name '_find_parallel_step'`

- [ ] **Step 3: Add `_find_parallel_step` recursive helper to `orchestrator/services/parallel.py`**

Add this function before `_resolve_branch_from_db` (around line 82):

```python
def _find_parallel_step(steps: StepList, group_name: str) -> Step | None:
    """Recursively search steps (and their parallel branches) for a parallel group name.

    Walks the step tree depth-first, checking each step's ``_parallel_group_name``
    attribute. Also recurses into ``_parallel_branches`` (static parallel) and
    ``_foreach_branch_template`` (foreach_parallel).

    Args:
        steps: A StepList (iterable of Step functions) to search.
        group_name: The parallel group name to find.

    Returns:
        The Step with matching ``_parallel_group_name``, or None if not found.
    """
    for s in steps:
        if getattr(s, "_parallel_group_name", None) == group_name:
            return s
        for branch in getattr(s, "_parallel_branches", []):
            found = _find_parallel_step(branch, group_name)
            if found is not None:
                return found
        template = getattr(s, "_foreach_branch_template", None)
        if template is not None:
            found = _find_parallel_step(template, group_name)
            if found is not None:
                return found
    return None
```

You'll need to add the `Step` import. Update the existing import block from `orchestrator.workflow`:

```python
from orchestrator.workflow import (
    _STATUSES,
    Step,
    StepList,
    StepStatus,
    Success,
    _exec_steps,
    _make_branch_dblogstep,
    _worst_status,
    reconstruct_branch,
)
```

- [ ] **Step 4: Update `_resolve_branch_from_db` to use `_find_parallel_step`**

Replace lines 109-114 in `orchestrator/services/parallel.py`:

```python
    # Before:
    parallel_step = next(
        (s for s in wf.steps if getattr(s, "_parallel_group_name", None) == parallel_group_name),
        None,
    )

    # After:
    parallel_step = _find_parallel_step(wf.steps, parallel_group_name)
```

The rest of `_resolve_branch_from_db` stays the same.

- [ ] **Step 5: Run the `_find_parallel_step` tests to verify they pass**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py -k "test_find_parallel_step" -v`
Expected: All PASS

- [ ] **Step 6: Set `process_stat_var` in `run_worker_branch`**

In `orchestrator/services/parallel.py`, add to the imports:

```python
from orchestrator.workflow import (
    _STATUSES,
    ProcessStat,
    Step,
    StepList,
    StepStatus,
    Success,
    _exec_steps,
    _make_branch_dblogstep,
    _worst_status,
    process_stat_var,
    reconstruct_branch,
)
```

Then in `run_worker_branch`, after `_resolve_branch_from_db` (line 135) and before `branch_state = deepcopy(initial_state)` (line 137), add:

```python
    # Set process_stat_var so nested parallel branches can create fork steps
    # and dispatch to Celery workers (if EXECUTOR=WORKER).
    from orchestrator.workflows import get_workflow

    wf = get_workflow(process.workflow.name) if process else None
    if wf is not None:
        pstat = ProcessStat(
            process_id=process_id,
            workflow=wf,
            state=Success(initial_state),
            log=branch,
            current_user=user,
        )
        process_stat_var.set(pstat)
```

Note: `process` (the `ProcessTable` row) is already loaded inside `_resolve_branch_from_db`. To avoid a redundant query, refactor `_resolve_branch_from_db` to also return the `ProcessTable` object. Change the return type and body:

```python
def _resolve_branch_from_db(
    fork_step_id: UUID, process_id: UUID, branch_index: int
) -> tuple[str, StepList, ProcessTable]:
    """Derive the workflow key, branch step list, and process from the fork step in DB."""
    from orchestrator.workflows import get_workflow

    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is None:
        raise ValueError(f"Fork step {fork_step_id} not found")

    parallel_group_name = fork_step.name

    process = db.session.get(ProcessTable, process_id)
    if process is None:
        raise ValueError(f"Process {process_id} not found")

    workflow_key = process.workflow.name
    wf = get_workflow(workflow_key)
    if wf is None:
        raise ValueError(f"Workflow '{workflow_key}' not found")

    parallel_step = _find_parallel_step(wf.steps, parallel_group_name)
    if parallel_step is None:
        raise ValueError(f"Parallel group '{parallel_group_name}' not found in workflow '{workflow_key}'")

    return parallel_group_name, reconstruct_branch(parallel_step, branch_index), process
```

Then update `run_worker_branch` to use the new return value and set `process_stat_var`:

```python
def run_worker_branch(
    *,
    process_id: UUID,
    branch_index: int,
    fork_step_id: UUID,
    initial_state: dict,
    user: str,
    seed_state: dict | None = None,
) -> None:
    """Execute a single parallel branch in a distributed worker."""
    from orchestrator.workflows import get_workflow

    parallel_group_name, branch, process = _resolve_branch_from_db(fork_step_id, process_id, branch_index)

    # Set process_stat_var so nested parallel branches can create fork steps
    # and dispatch to Celery workers (if EXECUTOR=WORKER).
    wf = get_workflow(process.workflow.name)
    if wf is not None:
        pstat = ProcessStat(
            process_id=process_id,
            workflow=wf,
            state=Success(initial_state),
            log=branch,
            current_user=user,
        )
        process_stat_var.set(pstat)

    branch_state = deepcopy(initial_state)
    dblogstep = _make_branch_dblogstep(process_id, fork_step_id, branch_index, user, seed_state=seed_state)
    try:
        _exec_steps(branch, Success(branch_state), dblogstep)
    except Exception as e:
        logger.error("Celery branch execution failed", branch_index=branch_index, error=str(e))

    completed, total = _atomic_increment_completed(fork_step_id)

    logger.info(
        "Branch completed",
        branch_index=branch_index,
        completed=completed,
        total=total,
        parallel_group=parallel_group_name,
    )

    if total is not None and completed >= total:
        _join_and_resume(
            process_id=process_id,
            fork_step_id=fork_step_id,
            initial_state=initial_state,
            user=user,
        )
```

- [ ] **Step 7: Run all parallel tests**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_db.py -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add orchestrator/services/parallel.py test/unit_tests/test_parallel_stress.py
git commit -m "Add recursive branch search and process_stat_var setup for Celery workers"
```

---

### Task 3: Update existing stress test assertions for nested fork step counts

**Files:**
- Modify: `test/unit_tests/test_parallel_stress.py`

After the copy_context fix, nested parallel blocks now create fork steps at every level. Several existing tests assert `len(fork_steps) == 1` for nested parallel workflows. These must be updated.

- [ ] **Step 1: Update `test_two_level_nested_parallel` assertions**

In `test/unit_tests/test_parallel_stress.py`, find `test_two_level_nested_parallel` (around line 189). Update the docstring and assertions:

Remove the "Note: Inner parallel fork steps are not persisted..." paragraph from the docstring.

Change:
```python
        # DB: one fork step for "Outer" (inner parallel runs without DB tracking)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1
```

To:
```python
        # DB: two fork steps — "Outer" and "Inner"
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 2

        fork_by_name = {fs.name: fs for fs in fork_steps}
        assert set(fork_by_name.keys()) == {"Outer", "Inner"}

        outer_fork = fork_by_name["Outer"]
```

And add inner fork verification after the existing branch assertions:

```python
        # Inner fork step is now persisted too
        inner_fork = fork_by_name["Inner"]
        assert inner_fork.parallel_total_branches == 2
        assert inner_fork.parallel_completed_count == 2
        inner_relations = _get_relations(inner_fork.step_id)
        inner_branch_indices = {rel.branch_index for rel in inner_relations}
        assert inner_branch_indices == {0, 1}
```

- [ ] **Step 2: Update `test_three_level_nested_parallel` assertions**

Find `test_three_level_nested_parallel` (around line 261). Remove the "Note: Only the outermost fork step is tracked..." paragraph.

Change:
```python
        # DB: one fork step for "Top" (nested parallels run without DB tracking)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1
```

To:
```python
        # DB: three fork steps — "Top", "Mid", "Deep"
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 3

        fork_by_name = {fs.name: fs for fs in fork_steps}
        assert set(fork_by_name.keys()) == {"Top", "Mid", "Deep"}

        top_fork = fork_by_name["Top"]
```

And update remaining references from `top_fork = fork_steps[0]` to use `fork_by_name`:

```python
        # Verify each fork step has correct branch counts
        for name in ("Top", "Mid", "Deep"):
            assert fork_by_name[name].parallel_total_branches == 2
            assert fork_by_name[name].parallel_completed_count == 2
            relations = _get_relations(fork_by_name[name].step_id)
            branch_indices = {rel.branch_index for rel in relations}
            assert branch_indices == {0, 1}
```

- [ ] **Step 3: Update `test_error_in_inner_nested_parallel_propagates_to_outer` assertions**

Find `test_error_in_inner_nested_parallel_propagates_to_outer` (around line 998). Change:
```python
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1
```

To:
```python
        # Both outer and inner fork steps are created (inner parallel runs before failing)
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 2
```

- [ ] **Step 4: Update `test_error_in_foreach_parallel_nested_inside_parallel` assertions**

Find `test_error_in_foreach_parallel_nested_inside_parallel` (around line 1034). Change:
```python
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1
```

To:
```python
        # Both outer and inner (foreach) fork steps are created
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 2
```

- [ ] **Step 5: Update `test_retryable_step_inside_nested_parallel_returns_waiting` assertions**

Find `test_retryable_step_inside_nested_parallel_returns_waiting` (around line 1074). Change:
```python
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1
```

To:
```python
        # Both outer and inner fork steps are created
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 2
```

- [ ] **Step 6: Update `test_mixed_one_nested_group_fails_another_succeeds_outer_fails` assertions**

Find `test_mixed_one_nested_group_fails_another_succeeds_outer_fails` (around line 1112). Change:
```python
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 1
```

To:
```python
        # Outer + Inner OK + Inner Fail = 3 fork steps
        fork_steps = _get_fork_steps(pstat.process_id)
        assert len(fork_steps) == 3
```

- [ ] **Step 7: Run all stress tests**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add test/unit_tests/test_parallel_stress.py
git commit -m "Update stress test assertions for nested fork step persistence"
```

---

### Task 4: Type checking, linting, and final verification

**Files:**
- Read only: `orchestrator/workflow.py`, `orchestrator/services/parallel.py`, `test/unit_tests/test_parallel_stress.py`

- [ ] **Step 1: Run mypy on changed production files**

Run: `uv run mypy orchestrator/workflow.py orchestrator/services/parallel.py`
Expected: No errors

- [ ] **Step 2: Run mypy on changed test files**

Run: `uv run mypy test/unit_tests/test_parallel_stress.py`
Expected: No errors

- [ ] **Step 3: Run ruff on all changed files**

Run: `uv run ruff check orchestrator/workflow.py orchestrator/services/parallel.py test/unit_tests/test_parallel_stress.py`
Expected: No errors

- [ ] **Step 4: Run full parallel test suite**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_db.py -v`
Expected: All pass

- [ ] **Step 5: Run the broader test suite to check for regressions**

Run: `uv run pytest test/unit_tests/ -v --timeout=120`
Expected: All pass (or only pre-existing failures unrelated to parallel)

- [ ] **Step 6: Fix any issues found and commit**

If any type errors, lint errors, or test failures were found, fix them and commit:

```bash
git add -u
git commit -m "Fix type/lint/test issues from ContextVar propagation changes"
```

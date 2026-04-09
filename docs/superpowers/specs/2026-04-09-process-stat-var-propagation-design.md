# Fix ContextVar Propagation for Nested Parallel Execution

## Problem

`process_stat_var` (a `contextvars.ContextVar`) is set in `runwf()` on the main thread but is **not visible** inside parallel branch threads. Python's `ThreadPoolExecutor` does not propagate ContextVars to worker threads — each thread starts with an empty context. This is true across all supported Python versions (3.11–3.15).

### Impact

When a parallel branch contains a nested `parallel()` or `foreach_parallel()`, `_exec_parallel_branches()` reads `process_stat_var.get(None)` → `None`, causing:

1. **No fork step created** — `_create_fork_step` is skipped (process_id is None), so the nested parallel group is invisible in the DB
2. **No branch step logging** — `_run_branch` uses a no-op lambda instead of `_make_branch_dblogstep`, so individual branch step results are lost
3. **Celery routing silently broken** — nested parallel falls through to threadpool even when `EXECUTOR=WORKER`, because the `process_id is not None` guard in the match/case fails

This affects both execution paths:
- **Threadpool path** (`_run_threadpool_branches`): branch threads don't inherit ContextVars
- **Celery worker path** (`run_worker_branch`): Celery tasks run in fresh processes with no `process_stat_var` set at all

## Design

Three changes, each addressing one layer of the problem.

### 1. Threadpool Path — `copy_context()` Wrapper

Wrap each `executor.submit()` in `_run_threadpool_branches` with `contextvars.copy_context().run()`. Each branch gets its own isolated copy of the parent thread's context, making `process_stat_var` (and `step_log_fn_var` and any future ContextVars) available inside the branch.

```python
# Before
executor.submit(_run_branch, branch, initial_state, ...)

# After
executor.submit(copy_context().run, _run_branch, branch, initial_state, ...)
```

Each `copy_context()` call creates a fresh copy at call time, so branches are isolated from each other. Mutations to ContextVars inside a branch do not affect sibling branches or the parent.

### 2. Celery Worker Path — Set `process_stat_var`

`run_worker_branch` in `orchestrator/services/parallel.py` executes in a fresh Celery task process — there is no parent context to copy. We must explicitly construct a `ProcessStat` and set it in `process_stat_var` before calling `_exec_steps`.

`run_worker_branch` already has `process_id` and `user`. It already calls `_resolve_branch_from_db` which loads the `ProcessTable` and looks up the `Workflow`. We restructure slightly to:

1. Extract the `Workflow` object from the existing `_resolve_branch_from_db` call (currently it returns `(group_name, branch)` — extend it to also return the workflow, or look it up separately)
2. Construct a minimal `ProcessStat(process_id=..., workflow=..., state=Success(initial_state), log=branch, current_user=user)`
3. Call `process_stat_var.set(pstat)` before `_exec_steps`

After this, if a Celery worker's branch contains a nested parallel and `EXECUTOR=WORKER`, the nested parallel will correctly dispatch its inner branches as Celery tasks (fork steps are created, branch steps are logged, Celery routing works).

### 3. Celery Branch Reconstruction — Recursive Search

`_resolve_branch_from_db` currently searches only top-level `wf.steps` for a step with matching `_parallel_group_name`. Nested parallel steps are NOT in `wf.steps` — they're inside a parent parallel step's `_parallel_branches` metadata. When a Celery worker receives an inner branch task, it fails with "Parallel group not found".

Fix: make the search recursive. Walk the step tree depth-first:

```
wf.steps
  → for each step, check _parallel_group_name
  → if step has _parallel_branches, recurse into each branch's steps
  → if step has _foreach_branch_template, recurse into the template's steps
```

This is a small change to `_resolve_branch_from_db` — extract the linear scan into a recursive helper:

```python
def _find_parallel_step(steps: Iterable[Step], group_name: str) -> Step | None:
    """Recursively search steps (and their parallel branches) for a parallel group name."""
    for s in steps:
        if getattr(s, "_parallel_group_name", None) == group_name:
            return s
        # Search inside static parallel branches
        for branch in getattr(s, "_parallel_branches", []):
            found = _find_parallel_step(branch, group_name)
            if found is not None:
                return found
        # Search inside foreach_parallel template
        template = getattr(s, "_foreach_branch_template", None)
        if template is not None:
            found = _find_parallel_step(template, group_name)
            if found is not None:
                return found
    return None
```

Then `_resolve_branch_from_db` calls `_find_parallel_step(wf.steps, parallel_group_name)` instead of the current `next(s for s in wf.steps if ...)`.

**Name uniqueness**: Parallel group names must be unique within a workflow for Celery reconstruction to work. This is already effectively true — users name their parallel groups distinctly. We could add a validation check at workflow definition time, but that's a separate concern.

### Files Changed

| File | Change |
|------|--------|
| `orchestrator/workflow.py` | Add `copy_context` import; wrap `executor.submit` in `_run_threadpool_branches` |
| `orchestrator/services/parallel.py` | Add `_find_parallel_step` recursive helper; update `_resolve_branch_from_db` to use it; set `process_stat_var` in `run_worker_branch` |
| `test/unit_tests/test_parallel_stress.py` | Update nested parallel tests to assert inner fork steps ARE now persisted |

### What Does NOT Change

- `_run_branch` — unchanged, receives context via copy_context wrapper (threadpool) or via caller setting ContextVar (Celery)
- `_exec_parallel_branches` — unchanged, reads `process_stat_var` as before
- `_create_fork_step` / `_make_branch_dblogstep` — unchanged
- `_dispatch_worker_branches` — unchanged, Celery task signature stays the same
- `reconstruct_branch` — unchanged, still reads `_parallel_branches` / `_foreach_branch_template`
- DB schema — no migrations needed

### Correctness Considerations

**Thread safety of copy_context**: Each branch gets its own context copy. ContextVar mutations inside one branch are invisible to siblings and the parent. This is the intended use of `copy_context().run()`.

**Recursive nesting (threadpool)**: A branch running in a copied context that hits another parallel step will call `_run_threadpool_branches` again, which again calls `copy_context()` from the branch thread's context (which has `process_stat_var` set). Nesting works to arbitrary depth.

**Recursive nesting (Celery)**: After setting `process_stat_var` in `run_worker_branch`, if the branch contains a nested parallel and `EXECUTOR=WORKER`, it dispatches inner branches as Celery tasks. Each inner worker task calls `run_worker_branch`, which sets `process_stat_var` and calls `_resolve_branch_from_db`. The recursive search finds the inner parallel step. Nesting works to arbitrary depth.

**Parallel group name uniqueness**: The recursive search returns the first match. If two parallel groups at different nesting levels share the same name, the wrong step could be returned. This is a user error — parallel group names should be unique within a workflow. A validation check could be added but is out of scope for this fix.

**Performance of recursive search**: The step tree is typically shallow (2-3 levels) and small (tens of steps). The recursive search is negligible compared to the cost of DB operations and actual step execution.

### Testing

Update existing stress tests in `test/unit_tests/test_parallel_stress.py`:

1. **`test_two_level_nested_parallel`** — change assertion from 1 fork step to 2 (outer + inner); verify inner fork step has correct `parallel_total_branches` and relations
2. **`test_three_level_nested_parallel`** — change assertion from 1 fork step to 3 (all levels)
3. **Nested error propagation tests** — update fork step count assertions where inner fork steps are now created
4. **New test: inner fork step DB integrity** — verify inner fork step has correct `parallel_total_branches`, `parallel_completed_count`, branch indices, and order_ids
5. **New test: `_find_parallel_step` recursive search** — unit test the helper with 1-level, 2-level, 3-level nesting, and foreach_parallel templates
6. **New test: Celery worker path sets process_stat_var** — call `run_worker_branch` directly (real DB, no Celery transport), verify nested parallel fork steps appear in DB

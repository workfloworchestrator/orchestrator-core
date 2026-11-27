---
# tutorial | how-to | reference | explanation | mixed
diataxis: mixed
reviewed: false
---

# Plan: parallel steps TODOs
<!-- diataxis: mixed -->

Working plan for the `parallel-step-design` branch. Delete this file before the branch is merged.

Nothing from this branch has been released (latest tag: 5.6.0), so the migration
`2026-04-01_18a7c2676fd3_add_process_step_relations.py` and the Celery task names can still be changed in place.

Line numbers refer to commit `1eccf564`.

Each phase ends with a green `prek run --all-files`, `uv run pytest test/unit_tests` and the parallel integration tests.
Remove each TODO comment in the commit that resolves it.

## Phase 1: Correctness of the parallel group lookup
<!-- diataxis: how-to -->

Status: done.

Two parallel steps with the same name can currently mix up each other's branches. Fix that first.

- `services/parallel.py:128`: *is it guaranteed that parallel group names are unique?*
  No. The name is the lookup key for rebuilding a branch on a worker (`_find_parallel_step`, first match) and for
  inheriting successful branches from a prior failed fork (`_create_fork_step`, by `(process_id, name)`).

  Fix: `make_workflow` walks the step tree, including nested branches and `map_parallel` templates, and raises
  `ValueError` on a duplicate group name. `_find_parallel_step` uses the same walk. Tests: duplicates at the top
  level, nested in a branch, inside a template, and across `parallel`/`map_parallel`.
- Steps the walk can't see (no TODO). Wrappers from `conditional`, `steplens` and `focussteps` are visible only
  because `functools.wraps` copies the `_parallel_*` attributes; phase 4 makes that explicit. `step_group`,
  `callback_step` and user wrappers hide their steps: duplicate names go undetected, and a worker can't find the
  branch.

  Fix: a safety net in `_exec_parallel_branches`. When a process runs, the step found under the group name must carry
  this step's own branches, compared by identity because `conditional` returns a wrapper; otherwise raise
  `ValueError`. A hidden parallel step then fails on its first run instead of mixing up branches.

  Tests: `conditional` with a duplicate name, and running on the threadpool (predicate true and false) and worker
  paths; `step_group` failing the safety net; strict xfails for `step_group` and `callback_step` visibility until
  phase 4 adds `Step.sub_steps`. `callback_step` gets no run test, because it suspends before a parallel step in its
  action runs.
- Parallel steps nested in a `map_parallel` template (no TODO). The uniqueness check is per definition, but such a
  step creates one fork row per item, all with the same `(process_id, name, branch_kind)`, so a retry can inherit
  branches from a sibling item's failed fork. Out of scope for phase 1: scope the prior-fork lookup to the enclosing
  branch in a follow-up. `test_nested_parallel_in_map_parallel_retries_only_its_own_failed_branches` in
  `test_parallel_retry.py` is a strict xfail test of the intended behaviour.
- `workflow.py:642` (no TODO): `_create_fork_step` detects a prior fork with `branch_count.isnot(None)`. Match on
  `ProcessStepTable.branch_kind == branch_kind` instead, like `processes.py:380` and `enrich_process.py:76`.
- `services/parallel.py:269`: *retrieve fork_step at the start and raise if None?*
  Yes. `_join_and_resume` loads the fork step first, and logs the ids and raises `ValueError` when it is missing,
  instead of resuming the process with the parallel step unresolved.

## Phase 2: Transaction around the join
<!-- diataxis: how-to -->

Decision: one transaction for the increment and the fork update, committed right before the resume is handed off.

- `services/parallel.py:67`: *is this commit necessary?*
  `services/parallel.py:221`: *both functions commit; is that safe(r)?*
  Remove the commit from `_atomic_increment_completed`. Move the transaction boundary into `run_worker_branch`, around
  the increment and, for the last finisher, around collecting the branch results and updating the fork row. The row lock
  taken by `UPDATE … RETURNING` then lasts until that commit. Only the last finisher does extra work, so other branches
  wait only briefly.
- `services/parallel.py:276`: *remove commit? RESUME already commits.*
  Keep exactly one commit before calling the RESUME executor. Don't rely on the executor's `transactional()`: when it
  fails (for example "incorrect status to resume"), it rolls back the fork update too. The fork row then stays
  `waiting`, `_recoverwf` treats the parallel step as not done, and `_create_fork_step` only inherits branches from
  *failed* forks, so a manual resume runs every branch again. Write the reason in a comment in place of the TODO.
- `services/parallel.py:274`: *add `fork_step.save()`?*
  No. The row comes from `db.session.get`, so the session already tracks the change. Remove the TODO.
- `test/unit_tests/services/test_parallel.py:31, 45`: *remove tests of a private function.*
  These tests mock `db` and assert that `commit` is called, which this phase changes. Replace them with integration
  tests of `run_worker_branch` (executor mocked):
  - a branch that is not the last one increments the counter and doesn't resume;
  - the last finisher sets the fork's status/state from the worst branch and calls RESUME once;
  - a failing RESUME leaves the fork row resolved (committed).

  Phase 1 added two mock-based unit tests of `_join_and_resume` (missing fork step raises and logs the ids). Fold them
  into the same integration-test rewrite, asserting the behaviour through `run_worker_branch` instead of a mocked `db`.

**Out of scope:** a worker that crashes after its branch steps are committed and before the join leaves the process
stuck in Waiting. See [Open points](#open-points). Add a test here that documents the current behaviour, so the
follow-up has a starting point.

## Phase 3: Branch results and branch lookup
<!-- diataxis: how-to -->

- `services/parallel.py:91`: *convert status to `Process` in `_collect_branch_results`.*
  `workflow.py:800`: *`type: ignore[attr-defined]` — fix this in `_collect_branch_results`.*
  - Return `dict[int, Process]` (branch index → latest result). Build it once with
    `_STATUSES.get(StepStatus(status), Success)(state)`.
  - Callers drop their own conversion: `_join_and_resume`, `_run_threadpool_branches`, and `_succeeded_branch_indices`
    (which becomes an `issuccess()` filter).
  - Remove `_STATUSES` from the import in `workflow.py:800`. It is defined in `workflow.py` itself and was only
    re-imported through `services/parallel.py`, which is what caused the mypy error. The `type: ignore` goes with it.
  - Let `_create_fork_step` (`workflow.py:648–668`) reuse the same "latest relation per branch" logic instead of its
    own copy.
- `services/parallel.py:160, 167`: *select the step name and workflow name directly.*
  Use two scalar selects (`ProcessStepTable.name` by `fork_step_id`; the workflow name by `process_id`, joined through
  `ProcessTable.workflow`). Drop `process` from the return value of `_resolve_branch_from_db`, because the caller
  doesn't use it. Keep the "not found" `ValueError`s and their tests.
- `services/parallel.py:212`: *is the global var necessary?*
  Yes. `_exec_parallel_branches` (`workflow.py:875`) reads `process_id`, `current_user` and `workflow.name` from it to
  support nested parallel steps on a worker. Replace the TODO with a comment saying so, and that `state`/`log` of this
  `ProcessStat` are placeholders. Add a test with a nested parallel step on the worker path, if none exists yet.

## Phase 4: Typed step metadata
<!-- diataxis: how-to -->

- `services/parallel.py:107, 130`: *make the step metadata check type-safe.*
  (`_child_step_lists` moved to `workflow.py:268` in phase 1, so the second one is now `workflow.py:268`;
  `_find_parallel_step` is `services/parallel.py:123`.)
  `workflow.py:943, 1092`: *fix untyped/undefined variables.*
  - Add a frozen dataclass `BranchSpec(name: str, kind: BranchKind, branches: tuple[StepList, ...])` in `workflow.py`,
    next to `BranchKind`. For template kinds (`MAP_PARALLEL`, and later `LOOP` from #1947), `branches` holds the single
    template.
  - Keep `BranchSpec` generic, so loop steps can reuse it: it holds the structure of a branching step, not how it runs.
    Execution options (`max_concurrency` and the items key of `map_parallel`; `until`, `limit` and `on_error` of a
    loop) stay in the step function built by the beta DSL, as `max_concurrency` does today. The stable class then doesn't
    change when a beta API changes.
  - Add `branching: BranchSpec | None = None` to the `Step` Protocol, in the same way as `importance` and
    `retry_auth_callback`, and set it through a new `make_step_function` parameter.
  - This replaces `_parallel_branches`, `_foreach_branch_template` and `_parallel_group_name`, along with every
    `getattr` and `type: ignore`. `reconstruct_branch` and `_child_step_lists` become `BranchSpec` methods;
    `reconstruct_branch` returns the template for template kinds.
  - Add `sub_steps: StepList | None = None` to the `Step` Protocol, set by `step_group` (and so by `callback_step`).
    `_child_step_lists` yields from both `branching.branches` and `sub_steps`. Remove the xfail markers of the
    `step_group` and `callback_step` tests from phase 1.
  - Add one helper that rewraps a step and copies all its `Step` attributes (`form`, `assignee`, both auth callbacks,
    `importance`, `branching`, `sub_steps`). Use it in `conditional` and `steplens` (and so `focussteps`) instead of
    calling `make_step_function` with a subset: its `None` default would erase `branching`, hiding a wrapped parallel
    step from the walk and from the worker. This also fixes an existing bug: `conditional` and `steplens` drop
    `retry_auth_callback` and `resume_auth_callback` today. Mention that fix in the release notes.
  - The duplicate-name check and the safety net from phase 1 use `BranchSpec`; the safety net compares
    `branching is spec`.
  - `BranchSpec`, the tree walk and the uniqueness check stay in stable code after phase 7, see
    [Parallel steps](package-structure.md#parallel-steps) in the package structure design.
  - Optional, same commit series: move `_is_callback_step` (`workflow.py:921`, `:1153`) to a typed attribute as well.

## Phase 5: Database and API
<!-- diataxis: how-to -->

Status: done.

## Phase 6: Public API and defaults
<!-- diataxis: how-to -->

Status: done.

`max_concurrency` applies only to threadpool execution and defaults to `MAX_WORKERS`. Each fork is bounded by
`max(1, (capacity - max(4, capacity // 4)) // MAX_WORKERS - 1)`, where capacity is `pool_size + max_overflow`.
The fixed reserve protects HTTP/scheduler and other non-fork users of the synchronous database connection pool, but
does not guarantee against database connection pool exhaustion. Pending requests above the budget are throttled;
explicit requests warn per fork and defaults once per process and `(capacity, MAX_WORKERS)` pair. Nested forks are not
globally bounded. Worker execution ignores this option and dispatches one Celery task per branch.


## Phase 7: Restructure
<!-- diataxis: how-to -->

Status: done.

Do this last, as pure moves, so the earlier diffs stay readable.

**Deviations from the destination table in [Parallel steps](package-structure.md#parallel-steps), both recorded there:**

- `reconstruct_branch` and `branch_step_name` live in `branching.py`, not `dsl.py`: they rebuild and name a branch
  from a `BranchSpec`, which `branching.py` owns, and `worker.py` needs them without importing the DSL. The module
  graph stays acyclic: `dsl → engine → {threadpool, worker} → branching`.
- `_dispatch_worker_branches` stayed in `worker.py`, next to `run_worker_branch`, mirroring how `threadpool.py` holds
  both `_run_threadpool_branches` (parent side) and `_run_branch` (branch side). `engine.py` is executor selection
  only.

**Still open:** the nested parallel steps decision below. The worker code moved regardless, since this phase changes
no behaviour; the decision changes what `worker.py` does, not where it lives.

- `workflow.py:701`: *move to a separate module along with `_exec_parallel_branches` and make it public.*
  `workflow.py:866`: *move to a separate module with submodules for the threadpool/Celery executor.*
  - Move the code to `orchestrator/core/beta/parallel/` (`__init__.py`, `dsl.py`, `branching.py`, `engine.py`,
    `threadpool.py`, `worker.py`), following
    [Parallel steps](package-structure.md#parallel-steps) in the package structure design. That section
    also lists what stays in stable code (data model, API fields, `BranchKind`, settings, Celery wiring).
  - Remove `parallel` from `orchestrator.core.__all__` and from `orchestrator.core.workflow`. Users import from
    `orchestrator.core.beta.parallel`. Update the examples in `docs/architecture/application/workflow.md` and mark
    those sections `{: .beta }`.
  - This ends the import cycle between `workflow.py` and `services/parallel.py`, and the function-level imports that
    work around it.
- `test/unit_tests/test_workflow.py:131`: *move this test when `_dispatch_worker_branches` is moved, and fix the DB
  error.* Fix the DB error now (phase 3): patch `_succeeded_branch_indices`, which is the function hitting the DB, and
  remove the `xfail`. Move the test along with the code in this phase.
- `test/integration_tests/test_parallel_*.py` (6 files): *move to the correct place, or to acceptance tests.*
  Move them together with the code above, so they only move once:

  | File | Destination |
  |---|---|
  | `test_parallel_celery_integration.py`, `test_parallel_retry.py` | `integration_tests/beta/parallel/`, as tests of `worker.py` |
  | `test_parallel_db.py`, `test_parallel_workflow.py`, `test_parallel_executor.py` | `integration_tests/beta/parallel/` (merge the single test in `test_parallel_executor.py` into one of the others) |
  | `test_parallel_stress.py` | `acceptance_tests/`, or `integration_tests/beta/parallel/` behind a slow marker; replace its use of the private `_find_step_by_group_name` |
  | `test/unit_tests/services/test_parallel.py`, parallel tests in `test/unit_tests/test_workflow.py` | `unit_tests/beta/parallel/` |

## Not part of this plan
<!-- diataxis: reference -->

- `orchestrator/core/workflows/utils.py:124` (translations, #549): unrelated to this branch.

## Open points
<!-- diataxis: how-to -->

These open points are tracked in
[workfloworchestrator/orchestrator-core#1780](https://github.com/workfloworchestrator/orchestrator-core/issues/1780):

- **Worker crash before the parallel join:** a worker that crashes after its branch steps are committed and before the
  join leaves the process stuck in `Waiting`. Determine how to detect and recover this state, and add a test that
  documents the current behaviour.
- **Nested parallel steps on the worker path:** an outer branch stops with `Waiting` at a nested parallel step, but
  completing the inner fork resumes the whole process instead of the outer branch. Confirm the behaviour with separate
  Celery workers and Redis, then either resume the parent branch correctly or reject nested parallel steps on the
  worker path until supported. Decide this before phase 7 moves the worker code to `beta/parallel/worker.py`.

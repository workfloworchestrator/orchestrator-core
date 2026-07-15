# Parallel Step Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 10 verified review findings on the `parallel-step-design` branch: make WORKER-mode join idempotent and transactional, align branch persistence with `safe_logstep` semantics, fix `_worst_status`, stop `__replace_last_state` from clobbering branch rows, and tighten efficiency/consistency details.

**Architecture:** All fixes stay inside the existing parallel-execution design (fork step + `ProcessStepRelationTable` + atomic counter join). The key structural changes: (1) the engine's "last step" lookup learns to ignore fork/branch auxiliary rows so `__replace_last_state` is safe; (2) WORKER mode pre-writes the Waiting main step *before* dispatching branches, eliminating the join-before-persist race; (3) the parallel step becomes resume-aware — a pending fork is awaited or joined inline, never re-dispatched; (4) the last-finisher's increment+join becomes a single transaction.

**Tech Stack:** SQLAlchemy 2, Celery, pytest (+testcontainers Postgres), structlog.

---

### Task 0: Baseline

- [ ] Run `uv run pytest test/integration_tests/test_parallel_workflow.py test/integration_tests/test_parallel_db.py test/unit_tests/test_parallel_join.py test/unit_tests/test_parallel_celery.py -q` and record pass/fail as the baseline.

### Task 1: `_worst_status` covers Abort; join parses statuses defensively (finding 3)

**Files:**
- Modify: `orchestrator/core/workflow.py:510` (`_STATUS_PRIORITY`)
- Modify: `orchestrator/core/services/parallel.py:258` (`_join_and_resume` status parse)
- Test: `test/unit_tests/test_parallel_join.py`

- [ ] **Step 1: failing tests** — parametrized: `_worst_status([Success, Abort]) is the Abort result`; priority order failed > abort > waiting > suspend > awaiting_callback; `_branch_results_to_processes` (new helper) maps unknown status string to `Failed` instead of raising.
- [ ] **Step 2: implementation**

```python
# workflow.py
_STATUS_PRIORITY: list[str] = ["isfailed", "isabort", "iswaiting", "issuspend", "isawaitingcallback"]
```

```python
# parallel.py — extract helper used by _join_and_resume
def _branch_results_to_processes(branch_data: list[tuple[int, dict, str]]) -> list[Process]:
    """Rebuild branch Process results from persisted (branch_index, state, status) rows.

    Unknown status strings (e.g. after DB corruption) become Failed so the join
    resolves to a visible failure instead of crashing and leaving the process stuck.
    """
    def to_process(branch_idx: int, state: dict, status: str) -> Process:
        if (process := Process.from_status(status, state)) is None:
            logger.error("Unknown branch step status", branch_index=branch_idx, status=status)
            return Failed({"error": f"Branch {branch_idx} has unknown step status {status!r}"})
        return process

    return [to_process(*row) for row in branch_data]
```
(`Process` and `Failed` are importable from `orchestrator.core.workflow`; drop the now-unused `_STATUSES`/`StepStatus` parse in `_join_and_resume`.)

- [ ] **Step 3: run tests, commit**

### Task 2: explicit branch selection + bounded thread pool (findings 7 & 5)

**Files:**
- Modify: `orchestrator/core/workflow.py:700-717` (`_run_threadpool_branches`)
- Modify: `orchestrator/core/settings.py` (new setting)
- Test: `test/integration_tests/test_parallel_workflow.py` (existing suite must stay green); unit test for worker-count derivation if extracted.

- [ ] **Step 1: implementation**

```python
# settings.py (near MAX_WORKERS)
PARALLEL_BRANCH_MAX_WORKERS: int = 10  # per-parallel-step thread cap (threadpool executor)
```

```python
# workflow.py
workers = max_workers if max_workers is not None else min(n_branches, app_settings.PARALLEL_BRANCH_MAX_WORKERS)
...
# foreach_parallel passes a single template branch with N seeds; static parallel
# passes N branches with no seeds (mirrors reconstruct_branch()).
branches[idx] if seeds is None else branches[0],
```
(`app_settings` import already available via local import in `_exec_parallel_branches`; move/keep import accordingly.)

- [ ] **Step 2: run threadpool suite, commit**

### Task 3: stop `__replace_last_state` clobbering; fork/branch rows excluded from "last step" (finding 10)

**Files:**
- Modify: `orchestrator/core/services/processes.py:244-249` (`_get_current_step_to_update` last-step query)
- Modify: `orchestrator/core/workflow.py:734-743` (`_run_threadpool_branches` return value)
- Modify: `test/integration_tests/test_parallel_celery_integration.py:300-311` (test that asserts the clobbering)
- Modify: `docs/designs/parallel-workflow-execution.md:336`
- Test: `test/integration_tests/test_parallel_workflow.py` — new test asserting the step before the parallel block is still present in the log and the parallel group row is appended.

- [ ] **Step 1: failing test** — run a `seq_before >> parallel(...) >> done` workflow with the in-memory `store` logger; assert log contains BOTH `"Sequential Before"` and the group name.
- [ ] **Step 2: implementation**

```python
# processes.py — last_db_step must be a *main-log* row: fork steps and branch child
# rows (see _is_main_log_step) are auxiliary and must never be replaced/deduped.
last_db_step = db.session.scalars(
    select(ProcessStepTable)
    .where(ProcessStepTable.process_id == p.process_id)
    .where(ProcessStepTable.parallel_total_branches.is_(None))
    .where(~exists().where(ProcessStepRelationTable.child_step_id == ProcessStepTable.step_id))
    .order_by(ProcessStepTable.completed_at.desc())
    .limit(1)
).first()
```

```python
# workflow.py — _run_threadpool_branches: the parallel step gets its own main-log row;
# branch steps live in separate rows linked via ProcessStepRelationTable.
return Success(initial_state)
```
(Remove `parallel_start_time`/`__replace_last_state`; the engine already stamps `__last_step_started_at` before the step runs, so duration spans branch execution.)

- [ ] **Step 3: update the celery integration test comment/assertions and design doc; run suites; commit**

### Task 4: WORKER-mode race — pre-write Waiting step; resume-aware fork (finding 1)

**Files:**
- Modify: `orchestrator/core/workflow.py` (`_dispatch_worker_branches`, `_exec_parallel_branches`)
- Modify: `orchestrator/core/services/parallel.py` (`_update_main_parallel_step` warning, new `find_pending_fork_id` / `resolve_pending_fork`)
- Test: `test/integration_tests/test_parallel_celery_integration.py`

- [ ] **Step 1: failing tests**
  - join-before-persist race: dispatch in WORKER mode (eager); the Waiting main row exists *before* branches run, so `_update_main_parallel_step` finds and resolves it without the test's manual fix-up.
  - resume of a pending fork does NOT create a second fork step / re-dispatch; with counter complete it resolves inline.
- [ ] **Step 2: implementation**

```python
# workflow.py — _dispatch_worker_branches: persist the Waiting main step BEFORE
# dispatching so the last-finisher join can never miss it (fixes join/persist race).
waiting_state = initial_state | {"__parallel_waiting": True, "__fork_step_id": str(fork_step_id)}
_write_waiting_main_step(process_id, name, waiting_state, current_user)
... dispatch loop unchanged ...
# __replace_last_state makes the engine update the pre-written row instead of appending.
return Waiting(waiting_state | {"__replace_last_state": True})
```

```python
# workflow.py — new helper next to _create_fork_step
def _write_waiting_main_step(process_id: UUID, name: str, state: State, current_user: str) -> None:
    """Persist the parallel group's Waiting main-log row before dispatching branches."""
    with db.database_scope():
        db.session.add(
            ProcessStepTable(
                process_id=process_id, name=name, status=StepStatus.WAITING,
                state=state, created_by=current_user,
            )
        )
        db.session.commit()
```

```python
# parallel.py — pending-fork detection (query mirrors _update_main_parallel_step)
def find_pending_fork_id(process_id: UUID, group_name: str) -> UUID | None:
    """Return the fork_step_id of a dispatched-but-unresolved parallel group, if any."""
    waiting_step = (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == process_id,
            ProcessStepTable.name == group_name,
            ProcessStepTable.status == StepStatus.WAITING,
            ProcessStepTable.parallel_total_branches.is_(None),
        )
        .order_by(ProcessStepTable.completed_at.desc())
        .first()
    )
    fork_id = (waiting_step.state or {}).get("__fork_step_id") if waiting_step else None
    return UUID(fork_id) if fork_id else None


def resolve_pending_fork(fork_step_id: UUID, initial_state: dict) -> Process:
    """Resolve a previously dispatched fork on resume without re-dispatching branches.

    Still running -> Waiting again. All branches finished -> join inline (repairs a
    join that crashed after the counter filled).
    """
    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is None:
        return Failed(initial_state | {"error": f"Fork step {fork_step_id} not found"})
    completed = fork_step.parallel_completed_count or 0
    total = fork_step.parallel_total_branches or 0
    waiting_state = initial_state | {"__parallel_waiting": True, "__fork_step_id": str(fork_step_id)}
    if completed < total:
        return Waiting(waiting_state | {"__replace_last_state": True})
    results = _branch_results_to_processes(_collect_branch_results(fork_step_id))
    worst = _worst_status(results)
    resolved = worst.__class__ if worst is not None else Success
    fork_step.status = resolved("").status
    db.session.commit()
    return resolved(initial_state | {"__replace_last_state": True})
```

```python
# workflow.py — _exec_parallel_branches WORKER arm, before creating a new fork:
case ExecutorType.WORKER if process_id is not None:
    from orchestrator.core.services.parallel import find_pending_fork_id, resolve_pending_fork
    if (pending_fork_id := find_pending_fork_id(process_id, name)) is not None:
        return resolve_pending_fork(pending_fork_id, initial_state)
    ...create fork + dispatch as before...
```
(NOTE: fork creation moves inside the match arms so a pending fork short-circuits before a new fork row is created.)

```python
# parallel.py — _update_main_parallel_step: never silent
if main_step is None:
    logger.warning(
        "No Waiting main step found for parallel group; resume will repair via pending-fork detection",
        process_id=process_id, step_name=step_name, fork_step_id=fork_step_id,
    )
    return
```

- [ ] **Step 3: run celery integration suite; commit**

### Task 5: single-transaction join + Celery task session hygiene (finding 2)

**Files:**
- Modify: `orchestrator/core/services/parallel.py` (`_atomic_increment_completed`, `run_worker_branch`, `_join_and_resume`)
- Modify: `orchestrator/core/services/tasks.py` (`_run_parallel_branch`)
- Test: `test/integration_tests/test_parallel_celery_integration.py`

- [ ] **Step 1: implementation**

```python
# parallel.py — increment no longer commits; the caller owns the transaction so the
# last finisher commits counter + fork + main-step updates atomically.
def _atomic_increment_completed(fork_step_id: UUID) -> tuple[int, int | None]:
    stmt = (...unchanged...)
    completed, total = db.session.execute(stmt).one()
    return completed, total

# run_worker_branch:
completed, total = _atomic_increment_completed(fork_step_id)
is_last = total is not None and completed >= total
if not is_last:
    db.session.commit()  # release the fork row lock for other branches
logger.info("Branch completed", ...)
if is_last:
    _join_and_resume(...)  # commits once, covering increment + fork + main step
```

```python
# tasks.py — _run_parallel_branch: commit/rollback so psycopg3 autobegin never leaves
# the worker connection idle-in-transaction (same concern as start_process above).
try:
    run_worker_branch(...)
    db.session.commit()
except Exception as exc:
    db.session.rollback()
    local_logger.error("Parallel branch failed", ...)
    return None
```

- [ ] **Step 2: run celery suites; commit**

### Task 6: branch dblogstep parity with safe_logstep (finding 4)

**Files:**
- Modify: `orchestrator/core/workflow.py:521-566` (`_make_branch_dblogstep`)
- Modify: `orchestrator/core/services/parallel.py` (`run_worker_branch` passes broadcast)
- Modify: `orchestrator/core/services/tasks.py` (`get_process_broadcast_fn` helper; pass into `run_worker_branch`)
- Test: `test/integration_tests/test_parallel_workflow.py` / `test_parallel_celery_integration.py`

- [ ] **Step 1: failing tests** — branch step state is JSON-round-tripped (a non-serializable object in step output doesn't survive into the next step); a DB failure on logging records a Failed branch step instead of propagating; broadcast_func is called per branch step when provided.
- [ ] **Step 2: implementation**

```python
# workflow.py — _make_branch_dblogstep gains broadcast_func and safe_logstep semantics:
def branch_dblogstep(step_: Step, p: Process) -> Process:
    try:
        return _write_branch_step(step_, p)
    except Exception as e:
        logger.exception("Failed to save branch step", branch_index=branch_index, step=step_.name)
        db.session.rollback()
        return _write_branch_step(step_, Failed(error_state_to_dict(e)))

def _write_branch_step(step_: Step, p: Process) -> Process:
    step_state = p.unwrap()
    step_name = step_state.pop("__step_name_override", step_.name)
    # Same serialization round-trip as _db_log_step: plain dict, no live ORM objects.
    serialized_state = json_loads(json_dumps(step_state))
    child_step = ProcessStepTable(..., state=serialized_state, ...)
    ...add/flush/relation/commit as before...
    if broadcast_func:
        broadcast_func(process_id)
    return p.__class__(child_step.state)
```

```python
# tasks.py — module-level accessor:
def get_process_broadcast_fn() -> BroadcastFunc | None:
    """Broadcast function attached to the Celery app, if initialised."""
    return getattr(_celery, "process_broadcast_fn", None) if _celery else None
```
Wire: `run_worker_branch(...)` accepts `broadcast_func: BroadcastFunc | None = None` and passes it to `_make_branch_dblogstep`; `_run_parallel_branch` passes `process_broadcast_fn`. Threadpool path (`_run_branch`) keeps `None` — the engine broadcasts when the parallel step's own row is logged (documented in the docstring).

- [ ] **Step 3: run suites; commit**

### Task 7: eager-load step relations in `_get_process` (finding 6)

**Files:**
- Modify: `orchestrator/core/services/processes.py:412-425`
- Test: existing API/enrich tests must stay green.

- [ ] **Step 1: implementation**

```python
options=[
    joinedload(ProcessTable.steps).selectinload(ProcessStepTable.child_step_relations).joinedload(ProcessStepRelationTable.child_step),
    joinedload(ProcessTable.steps).selectinload(ProcessStepTable.parent_step_relations),
    joinedload(ProcessTable.process_subscriptions).joinedload(ProcessSubscriptionTable.subscription),
],
```
(`_is_main_log_step` touches `parent_step_relations` for every step in `load_process`; `enrich_step_details` touches `child_steps` for fork steps — both now loaded up front.)

- [ ] **Step 2: run enrich/process tests; commit**

### Task 8: document `parallel_completed_count` semantics (finding 8)

**Files:**
- Modify: `orchestrator/core/db/models.py:189-191`, `orchestrator/core/workflow.py` (`_update_fork_step` docstring)

- [ ] **Step 1: comments** — column comment: "number of branches that finished (any status, failures included); celery increments per finisher, threadpool sets it post-join; observability only, never read for join decisions."
- [ ] **Step 2: commit (with Task 9)**

### Task 9: restore sequential-task acceptance coverage (finding 9)

**Files:**
- Modify: `test/acceptance_tests/celery/test_with_pytest_celery.py`

- [ ] **Step 1: add test** — run all four task types in order against the same `process_id` (the pre-refactor scenario), keeping the parametrized per-task test.
- [ ] **Step 2: commit**

### Task 10: full verification

- [ ] `uv run pytest test/unit_tests -q`
- [ ] `uv run pytest test/integration_tests/test_parallel_workflow.py test/integration_tests/test_parallel_db.py test/integration_tests/test_parallel_celery_integration.py test/integration_tests/test_parallel_executor.py -q`
- [ ] `uv run mypy orchestrator`
- [ ] `uv run ruff check orchestrator && uv run ruff format --check orchestrator`
- [ ] Final commit.

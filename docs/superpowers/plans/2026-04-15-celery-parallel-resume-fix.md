# Celery Parallel Step Resume Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the bug where Celery worker resume after parallel step join immediately completes the workflow instead of continuing with remaining steps.

**Architecture:** On resume, `load_process` includes fork steps and branch steps in the main step log, inflating `stepcount` in `_recoverwf`. This causes `wf.steps[stepcount:]` to return an empty list, so the workflow has no remaining steps. The fix filters fork/branch steps from the main log and updates the main Waiting step to Success during join so `_recoverwf` correctly advances past the parallel step.

**Tech Stack:** Python, SQLAlchemy, pytest, orchestrator workflow engine

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `test/integration_tests/test_parallel_celery_integration.py` | Modify | Add test for resume after parallel join |
| `orchestrator/services/parallel.py` | Modify | Update `_join_and_resume` to mark main Waiting step as Success |
| `orchestrator/services/processes.py` | Modify | Filter fork/branch steps from main log in `load_process` |

---

### Task 1: Write the failing integration test

**Files:**
- Modify: `test/integration_tests/test_parallel_celery_integration.py`

This test exercises the full Celery resume flow: run workflow in WORKER mode, let branches execute, then simulate resume via `load_process` + `runwf` and verify the workflow completes correctly (doesn't skip steps).

- [ ] **Step 1: Write the failing test**

Add this test at the end of `test/integration_tests/test_parallel_celery_integration.py`:

```python
@pytest.mark.celery
def test_worker_resume_after_parallel_join_completes_workflow() -> None:
    """After all parallel branches finish in WORKER mode, resuming the workflow must
    execute the remaining steps (final_step >> done) instead of immediately completing.

    This is the end-to-end resume test:
    1. Start workflow in WORKER mode -> returns Waiting
    2. Branches execute synchronously (eager Celery)
    3. Last branch triggers _join_and_resume which calls resume
    4. Resume reconstructs state via load_process and runs remaining steps
    5. Workflow completes with final_step output in state
    """

    final_step_called = False

    @step("Resume Final")
    def resume_final_step() -> dict:
        nonlocal final_step_called
        final_step_called = True
        return {"resume_final": "done"}

    @workflow()
    def resume_test_wf():
        return init >> parallel("resume group", begin >> cel_branch_a, begin >> cel_branch_b) >> resume_final_step >> done

    from orchestrator.services.parallel import run_worker_branch as _original_run_worker_branch
    from orchestrator.services.processes import load_process, safe_logstep

    resume_processes: list[ProcessTable] = []

    def _capture_resume(process, user="test", **kwargs):
        """Capture the process for manual resume instead of dispatching Celery task."""
        resume_processes.append(process)

    capture_execution_context = {
        "start": lambda *a, **kw: None,
        "resume": _capture_resume,
        "validate": lambda *a, **kw: None,
    }

    def _scoped_run_worker_branch(**kwargs):
        with db.database_scope():
            _original_run_worker_branch(**kwargs)

    with (
        patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER),
        patch("orchestrator.services.parallel.run_worker_branch", _scoped_run_worker_branch),
        patch("orchestrator.services.processes.get_execution_context", return_value=capture_execution_context),
    ):
        # Need to register workflow manually for cleanup (database_scope commits break auto-cleanup)
        wf_table = store_workflow(resume_test_wf, name="resume_test_wf")
        ALL_WORKFLOWS["resume_test_wf"] = WorkflowInstanceForTests(resume_test_wf, "resume_test_wf")
        ALL_WORKFLOWS["resume_test_wf"].workflow_instance = wf_table

        try:
            # Phase 1: Start workflow with DB-persisted step logging
            pstat = create_process("resume_test_wf", [{}], "test_user")
            result = runwf(pstat, partial(safe_logstep))

            assert result.iswaiting(), f"Expected Waiting after WORKER dispatch, got: {result}"

            # Verify branches completed and resume was triggered
            fork_step = _get_fork_step(pstat.process_id)
            assert fork_step.parallel_completed_count == fork_step.parallel_total_branches
            assert len(resume_processes) == 1, f"Expected 1 resume call, got {len(resume_processes)}"

            # Phase 2: Simulate resume (what the Celery worker would do)
            process = resume_processes[0]
            loaded_pstat = load_process(process)

            # The remaining steps must include final_step and done, NOT re-include the parallel step
            remaining_names = [s.name for s in loaded_pstat.log]
            assert "resume group" not in remaining_names, (
                f"Parallel step should not be re-executed on resume, but found in remaining: {remaining_names}"
            )
            assert len(loaded_pstat.log) >= 1, f"Expected remaining steps after parallel, got: {remaining_names}"

            # Phase 3: Execute resume
            resume_result = runwf(loaded_pstat, partial(safe_logstep))

            assert_complete(resume_result), f"Expected Complete after resume, got: {resume_result}"
            assert final_step_called, "final_step was not executed during resume"

        finally:
            del ALL_WORKFLOWS["resume_test_wf"]
            delete_workflow(wf_table)
```

You will need these additional imports at the top of the file:

```python
from functools import partial

from orchestrator.db import ProcessTable, ProcessStepTable, db
from orchestrator.services.processes import create_process, safe_logstep
from orchestrator.workflow import (
    begin, done, foreach_parallel, init, parallel, step, workflow, runwf, ProcessStat,
)
from orchestrator.workflows import ALL_WORKFLOWS
from test.unit_tests.workflows import (
    WorkflowInstanceForTests, assert_complete, run_workflow, store_workflow, delete_workflow,
)
```

Merge with existing imports — don't duplicate what's already imported, only add what's missing (`partial`, `ProcessTable`, `create_process`, `safe_logstep`, `runwf`, `ProcessStat`, `ALL_WORKFLOWS`, `store_workflow`, `delete_workflow`).

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_worker_resume_after_parallel_join_completes_workflow -v
```

Expected: FAIL — the test should fail because `load_process` returns incorrect remaining steps (empty or wrong), and/or the workflow doesn't complete. The assertion `"resume group" not in remaining_names` or `assert_complete(resume_result)` should fail.

- [ ] **Step 3: Commit**

```bash
git add test/integration_tests/test_parallel_celery_integration.py
git commit -m "Add failing test: worker resume after parallel join skips remaining steps"
```

---

### Task 2: Fix `_join_and_resume` to update the main Waiting step

**Files:**
- Modify: `orchestrator/services/parallel.py:216-239`

When all branches complete, `_join_and_resume` must update the main process step (the one with `status=waiting`) to Success. Currently it only updates the fork step, leaving the main Waiting step unchanged. On resume, `_recoverwf` sees the Waiting step and doesn't advance past it correctly.

- [ ] **Step 1: Write the failing unit test for `_join_and_resume` behavior**

Add a test to `test/integration_tests/test_parallel_celery_integration.py` that verifies the main Waiting step is updated to Success after join:

```python
@pytest.mark.celery
def test_join_and_resume_updates_main_waiting_step() -> None:
    """_join_and_resume must update the main Waiting process step to Success.

    The main Waiting step is created by safe_logstep when the parallel step returns Waiting.
    After all branches complete, _join_and_resume must mark it as Success so that
    _recoverwf correctly advances past it on resume.
    """
    from orchestrator.services.parallel import run_worker_branch as _original_run_worker_branch
    from orchestrator.services.processes import create_process, safe_logstep

    resume_log: list[object] = []

    def _noop_resume(process, user="test", **kwargs):
        resume_log.append(process.process_id)

    noop_execution_context = {"start": lambda *a, **kw: None, "resume": _noop_resume, "validate": lambda *a, **kw: None}

    def _scoped_run_worker_branch(**kwargs):
        with db.database_scope():
            _original_run_worker_branch(**kwargs)

    @workflow()
    def join_update_wf():
        return init >> parallel("join group", begin >> cel_branch_a, begin >> cel_branch_b) >> done

    with (
        patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER),
        patch("orchestrator.services.parallel.run_worker_branch", _scoped_run_worker_branch),
        patch("orchestrator.services.processes.get_execution_context", return_value=noop_execution_context),
    ):
        wf_table = store_workflow(join_update_wf, name="join_update_wf")
        ALL_WORKFLOWS["join_update_wf"] = WorkflowInstanceForTests(join_update_wf, "join_update_wf")
        ALL_WORKFLOWS["join_update_wf"].workflow_instance = wf_table

        try:
            pstat = create_process("join_update_wf", [{}], "test_user")
            result = runwf(pstat, partial(safe_logstep))

            assert result.iswaiting()

            # The main Waiting step must now be updated to Success by _join_and_resume
            all_steps = _get_all_steps(pstat.process_id)
            waiting_steps = [s for s in all_steps if s.status == "waiting"]
            assert len(waiting_steps) == 0, (
                f"Expected no Waiting steps after join, but found: "
                f"{[(s.name, s.status) for s in waiting_steps]}"
            )

            # The fork step should be Success
            fork_step = _get_fork_step(pstat.process_id)
            assert fork_step.status == "success"

        finally:
            del ALL_WORKFLOWS["join_update_wf"]
            delete_workflow(wf_table)
```

- [ ] **Step 2: Run to verify it fails**

Run:
```bash
uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_join_and_resume_updates_main_waiting_step -v
```

Expected: FAIL — the main Waiting step is NOT updated by `_join_and_resume`.

- [ ] **Step 3: Implement the fix in `_join_and_resume`**

In `orchestrator/services/parallel.py`, modify `_join_and_resume` to update the main Waiting step:

```python
def _join_and_resume(
    *,
    process_id: UUID,
    fork_step_id: UUID,
    initial_state: dict,
    user: str,
) -> None:
    """Called by the last-finishing branch to determine status and resume the parent workflow."""
    branch_data = _collect_branch_results(fork_step_id)

    results = [_STATUSES.get(StepStatus(status), Success)(state) for _branch_idx, state, status in branch_data]
    worst = _worst_status(results)

    resolved_status = worst.status if worst is not None else StepStatus.SUCCESS

    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is not None:
        fork_step.status = resolved_status
        fork_step.state = initial_state

        # Update the main Waiting process step (created by safe_logstep) to reflect
        # branch completion. Without this, _recoverwf on resume would not advance
        # past the parallel step.
        _update_main_parallel_step(process_id, fork_step.name, fork_step_id, resolved_status, initial_state)

        db.session.commit()

    from orchestrator.services.processes import _get_process, get_execution_context

    process = _get_process(process_id)
    resume_func = get_execution_context()["resume"]
    resume_func(process, user=user)
```

Add the helper function above `_join_and_resume`:

```python
def _update_main_parallel_step(
    process_id: UUID,
    step_name: str,
    fork_step_id: UUID,
    status: str,
    state: dict,
) -> None:
    """Update the main Waiting process step to reflect parallel branch completion.

    When the parallel step dispatches branches in WORKER mode, safe_logstep writes a
    Waiting process step. After all branches complete, this step must be updated to
    the resolved status so _recoverwf correctly advances past it on resume.
    """
    from sqlalchemy import and_

    main_step = (
        db.session.query(ProcessStepTable)
        .filter(
            and_(
                ProcessStepTable.process_id == process_id,
                ProcessStepTable.name == step_name,
                ProcessStepTable.status == StepStatus.WAITING,
                ProcessStepTable.step_id != fork_step_id,
            )
        )
        .first()
    )
    if main_step is not None:
        main_step.status = status
        main_step.state = state
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_join_and_resume_updates_main_waiting_step -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/services/parallel.py test/integration_tests/test_parallel_celery_integration.py
git commit -m "Fix _join_and_resume to update main Waiting step after parallel branch completion"
```

---

### Task 3: Fix `load_process` to filter fork and branch steps

**Files:**
- Modify: `orchestrator/services/processes.py:815-830`

Even with the Waiting step updated, fork steps and branch steps in `process.steps` inflate `stepcount` in `_recoverwf`. They must be filtered out of the main log before recovery.

- [ ] **Step 1: Write the failing test**

Add a test to `test/integration_tests/test_parallel_celery_integration.py`:

```python
@pytest.mark.celery
def test_load_process_excludes_fork_and_branch_steps() -> None:
    """load_process must not include fork steps or branch child steps in the recovered log.

    Fork steps (parallel_total_branches IS NOT NULL) and branch steps (linked via
    ProcessStepRelationTable) are auxiliary parallel tracking rows. Including them
    in the main log inflates stepcount in _recoverwf, causing steps to be skipped.
    """
    from orchestrator.services.processes import load_process

    @workflow()
    def load_process_wf():
        return init >> parallel("lp group", begin >> cel_branch_a, begin >> cel_branch_b) >> final_step >> done

    with WorkflowInstanceForTests(load_process_wf, "load_process_wf"):
        result, pstat, _step_log = run_workflow("load_process_wf", [{}])
        assert_complete(result)

        # Verify fork step and branch steps exist in DB
        fork_step = _get_fork_step(pstat.process_id)
        assert fork_step is not None
        all_steps = _get_all_steps(pstat.process_id)
        branch_steps = [s for s in all_steps if s.parent_step_relations]
        assert len(branch_steps) >= 2, "Expected at least 2 branch steps in DB"

        # load_process should recover only main log steps
        process = db.session.get(ProcessTable, pstat.process_id)
        loaded = load_process(process)

        # The recovered state should be Complete (workflow finished)
        assert loaded.state.iscomplete(), f"Expected Complete state, got: {loaded.state}"

        # The remaining log should be empty (all steps executed)
        assert len(loaded.log) == 0, f"Expected no remaining steps, got: {[s.name for s in loaded.log]}"
```

- [ ] **Step 2: Run to verify it fails**

Run:
```bash
uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_load_process_excludes_fork_and_branch_steps -v
```

Expected: FAIL — `load_process` includes fork/branch steps, inflating stepcount. The recovered state or remaining log will be wrong.

- [ ] **Step 3: Implement the fix in `load_process`**

In `orchestrator/services/processes.py`, modify `load_process` to filter out fork steps and branch steps:

```python
def _is_main_log_step(step: ProcessStepTable) -> bool:
    """Return True if this step is part of the main workflow log.

    Excludes fork steps (parallel tracking) and branch child steps
    (linked via ProcessStepRelationTable). These are auxiliary rows
    that must not inflate the step count in _recoverwf.
    """
    if step.parallel_total_branches is not None:
        return False
    if step.parent_step_relations:
        return False
    return True


def load_process(process: ProcessTable) -> ProcessStat:
    workflow = get_workflow(str(process.workflow.name))

    if not workflow:
        workflow = removed_workflow

    main_steps = [s for s in process.steps if _is_main_log_step(s)]
    log = _restore_log(main_steps)
    pstate, remaining = _recoverwf(workflow, log)

    return ProcessStat(
        process_id=process.process_id,
        workflow=workflow,
        state=pstate,
        log=remaining,
        current_user=SYSTEM_USER,
    )
```

Add `_is_main_log_step` directly above `load_process` in the file.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_load_process_excludes_fork_and_branch_steps -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/services/processes.py test/integration_tests/test_parallel_celery_integration.py
git commit -m "Filter fork and branch steps from main log in load_process"
```

---

### Task 4: Verify the full resume test passes

**Files:**
- Test: `test/integration_tests/test_parallel_celery_integration.py`

With both fixes in place (Task 2 + Task 3), the end-to-end resume test from Task 1 should now pass.

- [ ] **Step 1: Run the full resume test**

Run:
```bash
uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_worker_resume_after_parallel_join_completes_workflow -v
```

Expected: PASS — the workflow resumes correctly after parallel join, executes `resume_final_step`, and reaches Complete state.

- [ ] **Step 2: Run all parallel celery integration tests**

Run:
```bash
uv run pytest test/integration_tests/test_parallel_celery_integration.py -v
```

Expected: ALL tests pass (existing + new).

- [ ] **Step 3: Run the full integration test suite**

Run:
```bash
uv run pytest test/integration_tests/ -v
```

Expected: No regressions. The `load_process` change must not break any existing resume/recovery behavior.

- [ ] **Step 4: Run type checking**

Run:
```bash
uv run mypy orchestrator/services/parallel.py orchestrator/services/processes.py
```

Expected: No type errors.

- [ ] **Step 5: Commit (if any fixups needed)**

Only if adjustments were needed during verification:

```bash
git add -u
git commit -m "Fix integration test issues from resume fix verification"
```

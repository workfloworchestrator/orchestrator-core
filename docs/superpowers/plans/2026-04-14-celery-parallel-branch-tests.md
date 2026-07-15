# Celery Parallel Branch Integration Tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add integration tests that prove (1) `foreach_parallel` dispatches ALL branches to Celery (not just the first), and (2) a failed parallel branch results in a terminal Failed status without infinite retries.

**Architecture:** Both tests run with `EXECUTOR=WORKER` and `task_always_eager=True` (synchronous Celery). They use the existing `WorkflowInstanceForTests` context manager and Celery test fixtures from `test/integration_tests/conftest.py`. A `unittest.mock.patch` on `app_settings.EXECUTOR` switches the engine to worker mode.

**Tech Stack:** pytest, orchestrator workflow DSL, SQLAlchemy, Celery (eager mode), unittest.mock

---

### Task 1: Test foreach_parallel dispatches all branches via Celery worker

**Files:**
- Modify: `test/integration_tests/test_parallel_celery_integration.py`

This test creates a `foreach_parallel` workflow over 3 items, runs it with `EXECUTOR=WORKER`, and asserts that all 3 branches are executed and persisted in the DB. The key assertion is that the fork step's `parallel_completed_count` equals the number of items, and all branch results are present.

- [ ] **Step 1: Write the failing test**

Add these imports and step definitions at the top of `test_parallel_celery_integration.py` (after the existing imports and step definitions):

```python
from unittest.mock import patch

from orchestrator.settings import ExecutorType, app_settings
```

Then add the test at the end of the file:

```python
@pytest.mark.celery
def test_foreach_parallel_worker_dispatches_all_branches() -> None:
    """With EXECUTOR=WORKER, foreach_parallel must dispatch and execute every branch, not just the first."""

    call_log: list[int] = []

    @step("Track FE Item")
    def track_fe_item(item: object, item_index: int) -> dict:
        call_log.append(item_index)
        return {f"tracked_{item_index}": f"done_{item}"}

    @step("Seed FE Items Worker")
    def seed_fe_items_worker() -> dict:
        return {"items": ["x", "y", "z"]}

    @workflow()
    def fe_worker_wf():
        return init >> seed_fe_items_worker >> foreach_parallel("fe worker group", "items", begin >> track_fe_item) >> done

    with patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER):
        with WorkflowInstanceForTests(fe_worker_wf, "fe_worker_wf"):
            result, pstat, _step_log = run_workflow("fe_worker_wf", [{}])
            assert_complete(result)

            # All 3 branches must have been called
            assert sorted(call_log) == [0, 1, 2], f"Expected branches 0,1,2 but got {call_log}"

            # DB: fork step must show all branches completed
            fork_step = _get_fork_step(pstat.process_id)
            assert fork_step.parallel_total_branches == 3
            assert fork_step.parallel_completed_count == 3

            # DB: all branch results must be present
            branch_results = _collect_branch_results(fork_step.step_id)
            assert len(branch_results) == 3

            indices = {r[0] for r in branch_results}
            assert indices == {0, 1, 2}

            # Each branch produced its expected key
            all_state_keys = {key for _idx, state, _status in branch_results for key in state}
            assert "tracked_0" in all_state_keys
            assert "tracked_1" in all_state_keys
            assert "tracked_2" in all_state_keys
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_foreach_parallel_worker_dispatches_all_branches -v`

Expected: FAIL — the test should fail because Celery only picks up the first branch (the bug we're testing for). If the test passes, the bug is not reproducible under `task_always_eager=True` and we need to adjust (see Step 4).

- [ ] **Step 3: Evaluate result and adjust**

If the test **passes** (eager mode doesn't reproduce the bug): the bug only manifests with a real Celery worker. In that case, the test is still valuable as a regression guard. Add a comment at the top of the test:

```python
# NOTE: This test runs with task_always_eager=True (synchronous). The production bug
# (only first branch picked up) may require a real worker to reproduce. This test
# guards against regressions in the dispatch loop and branch reconstruction logic.
```

If the test **fails**: investigate the failure message to understand whether it's the dispatch loop (`_dispatch_worker_branches` not iterating all branches) or the branch reconstruction (`_resolve_branch_from_db` or `reconstruct_branch` failing for index > 0). Fix accordingly in a separate task.

- [ ] **Step 4: Commit**

```bash
git add test/integration_tests/test_parallel_celery_integration.py
git commit -m "Add integration test: foreach_parallel dispatches all branches via Celery worker"
```

---

### Task 2: Test parallel step failure results in Failed status without retry

**Files:**
- Modify: `test/integration_tests/test_parallel_celery_integration.py`

This test creates a `parallel` workflow where one branch raises an exception, runs it with `EXECUTOR=WORKER`, and asserts that:
1. The workflow reaches a terminal Failed state (not Waiting/retrying)
2. The failing branch task is only called once (no infinite retry)
3. The fork step in DB reflects the failure

- [ ] **Step 1: Write the failing test**

Add the test at the end of `test/integration_tests/test_parallel_celery_integration.py`:

```python
@pytest.mark.celery
def test_parallel_branch_failure_does_not_retry_with_worker() -> None:
    """A failed parallel branch must result in a Failed workflow, not infinite retries."""

    fail_call_count = 0

    @step("Always Fail")
    def always_fail() -> dict:
        nonlocal fail_call_count
        fail_call_count += 1
        raise RuntimeError("Intentional branch failure")

    @step("Always Succeed")
    def always_succeed() -> dict:
        return {"ok": True}

    @workflow()
    def fail_worker_wf():
        return init >> parallel("fail group", begin >> always_fail, begin >> always_succeed) >> done

    with patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER):
        with WorkflowInstanceForTests(fail_worker_wf, "fail_worker_wf"):
            result, pstat, _step_log = run_workflow("fail_worker_wf", [{}])

            # Workflow must reach a terminal non-success state
            assert not result.issuccess(), f"Expected failure but got success: {result}"
            assert not result.iswaiting(), f"Workflow stuck in Waiting (retry loop?): {result}"

            # The failing step must have been called exactly once — no retries
            assert fail_call_count == 1, f"Failing branch was called {fail_call_count} times, expected 1"

            # DB: fork step must reflect failure
            fork_step = _get_fork_step(pstat.process_id)
            assert fork_step.status == "failed"
            assert fork_step.parallel_completed_count == 2  # both branches ran to completion
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_parallel_branch_failure_does_not_retry_with_worker -v`

Expected: FAIL — the test should fail because the workflow engine keeps retrying (the bug). The `fail_call_count > 1` assertion or the `iswaiting()` assertion should trigger.

- [ ] **Step 3: Evaluate result and adjust**

If the test **fails as expected** (retry behavior confirmed): the test documents the bug. Add a `pytest.mark.xfail` with a reason if you want to keep it in CI without blocking:

```python
@pytest.mark.xfail(reason="Known bug: worker mode retries failed parallel branches instead of propagating failure")
```

If the test **passes**: the retry bug is not reproducible under eager mode. Keep the test as a regression guard and add a comment:

```python
# NOTE: The production retry bug may only manifest with a real Celery worker and
# task_acks_late=True or broker visibility_timeout. This test guards the in-process path.
```

- [ ] **Step 4: Commit**

```bash
git add test/integration_tests/test_parallel_celery_integration.py
git commit -m "Add integration test: parallel branch failure terminates without retry"
```

---

### Task 3: Test foreach_parallel failure with worker (error in one branch out of many)

**Files:**
- Modify: `test/integration_tests/test_parallel_celery_integration.py`

This test exercises error handling specifically in `foreach_parallel` (not just `parallel`), where one item's branch fails while others succeed.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.celery
def test_foreach_parallel_single_branch_failure_with_worker() -> None:
    """In foreach_parallel with EXECUTOR=WORKER, one failing branch must fail the whole workflow.

    All branches must still execute (no short-circuit), but the final status is Failed.
    """

    executed_indices: list[int] = []

    @step("Maybe Fail Item")
    def maybe_fail_item(item: object, item_index: int) -> dict:
        executed_indices.append(item_index)
        if item == "poison":
            raise RuntimeError(f"Branch {item_index} hit poison item")
        return {f"result_{item_index}": f"ok_{item}"}

    @step("Seed With Poison")
    def seed_with_poison() -> dict:
        return {"items": ["good", "poison", "fine"]}

    @workflow()
    def fe_fail_worker_wf():
        return (
            init
            >> seed_with_poison
            >> foreach_parallel("fe fail group", "items", begin >> maybe_fail_item)
            >> done
        )

    with patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER):
        with WorkflowInstanceForTests(fe_fail_worker_wf, "fe_fail_worker_wf"):
            result, pstat, _step_log = run_workflow("fe_fail_worker_wf", [{}])

            # All branches must have executed (no short-circuit)
            assert sorted(executed_indices) == [0, 1, 2], f"Expected all branches to run, got {executed_indices}"

            # Workflow must not be stuck retrying
            assert not result.iswaiting(), f"Workflow stuck in Waiting: {result}"

            # DB: fork step reflects failure
            fork_step = _get_fork_step(pstat.process_id)
            assert fork_step.parallel_completed_count == 3
            assert fork_step.status == "failed"

            # DB: branch results — 2 success, 1 failed
            branch_results = _collect_branch_results(fork_step.step_id)
            assert len(branch_results) == 3
            statuses = {r[0]: r[2] for r in branch_results}
            assert statuses[0] == "success"
            assert statuses[1] == "failed"
            assert statuses[2] == "success"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest test/integration_tests/test_parallel_celery_integration.py::test_foreach_parallel_single_branch_failure_with_worker -v`

Expected: FAIL if the retry bug applies to foreach_parallel too, or PASS if the dispatch works correctly.

- [ ] **Step 3: Evaluate and mark accordingly**

Same approach as Task 2: if the test fails because of the retry bug, mark with `xfail`. If it passes, keep as regression guard with a comment.

- [ ] **Step 4: Commit**

```bash
git add test/integration_tests/test_parallel_celery_integration.py
git commit -m "Add integration test: foreach_parallel single branch failure with worker"
```

---

### Task 4: Run all integration tests and verify no regressions

- [ ] **Step 1: Run the full integration test suite**

```bash
uv run pytest test/integration_tests/ -v --tb=short
```

Expected: All existing tests pass. New tests either pass (regression guards) or are marked `xfail` (documenting known bugs).

- [ ] **Step 2: Run linting and type checks**

```bash
uv run ruff check test/integration_tests/test_parallel_celery_integration.py
uv run mypy test/integration_tests/test_parallel_celery_integration.py
```

Fix any issues found.

- [ ] **Step 3: Final commit if needed**

```bash
git add test/integration_tests/test_parallel_celery_integration.py
git commit -m "Fix lint/type issues in parallel celery integration tests"
```

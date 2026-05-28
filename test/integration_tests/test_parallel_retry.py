# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Regression tests for parallel step retry semantics.

Covers three bugs surfaced by the SURF orchestrator parallel-demo workflow:

1. Threadpool path writes a duplicate "main-log" row for the parallel step
   in addition to the fork row, so a query by name on a failed parallel
   step finds two rows.
2. ``_create_fork_step`` is non-idempotent across retries: each retry inserts
   a fresh fork row, leaving the original fork (and its branch children)
   orphaned alongside the new one.
3. ``_update_main_parallel_step`` only matches ``status == WAITING``. After a
   failed retry, the old main-log row sits in ``failed`` state and is never
   updated to reflect the retry outcome.
"""

from functools import partial

import pytest

from orchestrator.core.db import ProcessStepTable, ProcessTable, db
from orchestrator.core.services.processes import create_process, load_process, safe_logstep
from orchestrator.core.workflow import (
    begin,
    done,
    init,
    parallel,
    runwf,
    step,
    workflow,
)
from test.integration_tests.workflows import WorkflowInstanceForTests


@step("Always Succeeds A")
def always_succeeds_a() -> dict:
    return {"a": "ok"}


@step("Always Succeeds B")
def always_succeeds_b() -> dict:
    return {"b": "ok"}


def _rows_with_name(process_id, name: str) -> list[ProcessStepTable]:
    """All process step rows for this process with the given name (any kind)."""
    return (
        db.session.query(ProcessStepTable)
        .filter(ProcessStepTable.process_id == process_id, ProcessStepTable.name == name)
        .all()
    )


def _fork_rows(process_id, name: str) -> list[ProcessStepTable]:
    """Fork rows (rows carrying parallel branch metadata) for this group on this process."""
    return (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == process_id,
            ProcessStepTable.name == name,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .all()
    )


@pytest.mark.workflow
def test_threadpool_failure_does_not_duplicate_main_log_row() -> None:
    """Bug 1: a failed parallel step in THREADPOOL mode must not leave two rows for the same name.

    Before the fix: the fork row stays as one row, and ``safe_logstep`` writes a second
    row with the same name carrying the worst-branch error state. After the fix: exactly
    one row exists for the parallel group name (the fork row, which doubles as the
    main-log entry for the parallel step).
    """

    @step("Boom")
    def boom() -> dict:
        raise ValueError("boom")

    @workflow()
    def failing_threadpool_wf():
        return init >> parallel("Fan out", begin >> always_succeeds_a, begin >> boom) >> done

    with WorkflowInstanceForTests(failing_threadpool_wf, "failing_threadpool_wf"):
        pstat = create_process("failing_threadpool_wf", [{}])
        result = runwf(pstat, partial(safe_logstep))
        assert result.isfailed(), f"expected failed, got {result}"

        rows = _rows_with_name(pstat.process_id, "Fan out")
        assert len(rows) == 1, (
            f"expected exactly one row named 'Fan out', got {len(rows)}: "
            f"{[(r.status, r.parallel_total_branches) for r in rows]}"
        )


@pytest.mark.workflow
def test_retry_preserves_history_and_only_reruns_failed_branches() -> None:
    """Retry must skip branches that already succeeded and preserve their prior rows.

    The ``always_succeeds`` branch must run exactly once across both attempts; the
    flaky branch must run twice (once failed, once succeeded). All four child
    rows (1 success + 1 failed + 1 success) are kept in the DB.
    """
    invocations: dict[str, int] = {"good": 0, "flaky": 0}

    @step("Counted Good")
    def counted_good() -> dict:
        invocations["good"] += 1
        return {"good": "ok"}

    @step("Counted Flaky")
    def counted_flaky() -> dict:
        invocations["flaky"] += 1
        if invocations["flaky"] == 1:
            raise ValueError("first attempt fails")
        return {"flaky": "ok"}

    @workflow()
    def selective_retry_wf():
        return init >> parallel("Fan out", begin >> counted_good, begin >> counted_flaky) >> done

    with WorkflowInstanceForTests(selective_retry_wf, "selective_retry_wf"):
        pstat = create_process("selective_retry_wf", [{}])
        result = runwf(pstat, partial(safe_logstep))
        assert result.isfailed()

        db.session.expire_all()
        retry_result = runwf(load_process(db.session.get(ProcessTable, pstat.process_id)), partial(safe_logstep))
        assert retry_result.iscomplete()

        assert invocations["good"] == 1, f"good branch should run once, ran {invocations['good']} times"
        assert invocations["flaky"] == 2, f"flaky branch should run twice, ran {invocations['flaky']} times"

        good_rows = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == pstat.process_id,
                ProcessStepTable.name == "[Branch 0] Counted Good",
            )
            .all()
        )
        flaky_rows = (
            db.session.query(ProcessStepTable)
            .filter(
                ProcessStepTable.process_id == pstat.process_id,
                ProcessStepTable.name == "[Branch 1] Counted Flaky",
            )
            .all()
        )
        assert len(good_rows) == 1, f"good branch row should appear once, found {len(good_rows)}"
        assert len(flaky_rows) == 2, f"flaky branch should have both attempts preserved, found {len(flaky_rows)}"
        assert sorted(r.status for r in flaky_rows) == ["failed", "success"]


@pytest.mark.workflow
def test_threadpool_retry_preserves_old_fork_and_adds_new_one() -> None:

    attempts = {"count": 0}

    @step("Flaky")
    def flaky() -> dict:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("first attempt fails")
        return {"flaky": "ok"}

    @workflow()
    def flaky_threadpool_wf():
        return init >> parallel("Fan out", begin >> always_succeeds_a, begin >> flaky) >> done

    with WorkflowInstanceForTests(flaky_threadpool_wf, "flaky_threadpool_wf"):
        pstat = create_process("flaky_threadpool_wf", [{}])
        result = runwf(pstat, partial(safe_logstep))
        assert result.isfailed(), f"expected first run to fail, got {result}"

        db.session.expire_all()
        process = db.session.get(ProcessTable, pstat.process_id)
        loaded_pstat = load_process(process)
        retry_result = runwf(loaded_pstat, partial(safe_logstep))
        assert retry_result.iscomplete(), f"expected retry to complete, got {retry_result}"

        forks = sorted(_fork_rows(pstat.process_id, "Fan out"), key=lambda f: f.completed_at)
        assert len(forks) == 2, (
            f"expected two fork rows (old failed + new success), got {len(forks)}: "
            f"{[(f.status, f.parallel_total_branches, f.parallel_completed_count) for f in forks]}"
        )
        assert [f.status for f in forks] == ["failed", "success"], (
            f"expected [failed, success] in completed_at order, got {[f.status for f in forks]}"
        )

        # The new fork must "see" all branches' final outcomes via inherited relations.
        new_fork = forks[-1]
        child_statuses = sorted(c.status for c in new_fork.child_steps)
        assert child_statuses == ["success", "success"], (
            f"new fork's child_steps should reflect all branches as success, got {child_statuses}"
        )

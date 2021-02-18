from datetime import timedelta

import pytest

from orchestrator.db import ProcessStepTable, ProcessTable, db
from orchestrator.utils.datetime import nowtz
from orchestrator.workflow import ProcessStatus
from test.unit_tests.workflows import assert_complete, assert_state, extract_state, run_workflow


@pytest.fixture
def task():
    three_weeks_ago = nowtz() - timedelta(weeks=3)
    two_weeks_ago = nowtz() - timedelta(weeks=2)
    state = {"foo": "bar"}

    generic_step = ProcessStepTable(name="generic-step", status="success", state=state)

    task_old = ProcessTable(
        workflow="nice and old task",
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=two_weeks_ago,
        steps=[generic_step],
        is_task=True,
    )

    task_new = ProcessTable(
        workflow="nice and new task",
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=nowtz(),
        steps=[generic_step],
        is_task=True,
    )

    process = ProcessTable(
        workflow="nice process",
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=two_weeks_ago,
        steps=[generic_step],
        is_task=False,
    )
    db.session.add(generic_step)
    db.session.add(task_old)
    db.session.add(task_new)
    db.session.add(process)
    db.session.commit()


@pytest.mark.workflow
def test_remove_tasks(task):
    result, process, step_log = run_workflow("task_clean_up_tasks", {})
    assert_complete(result)
    res = extract_state(result)
    state = {"process_id": res["process_id"], "reporter": "john.doe", "tasks_removed": 1}
    assert_state(result, state)

    processes = ProcessTable.query.all()

    assert len(processes) == 3
    assert sorted(p.workflow for p in processes) == sorted(["nice and new task", "nice process", "task_clean_up_tasks"])

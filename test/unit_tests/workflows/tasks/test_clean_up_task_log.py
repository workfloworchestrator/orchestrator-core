from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from orchestrator.db import ProcessStepTable, ProcessTable, WorkflowTable, db
from orchestrator.targets import Target
from orchestrator.utils.datetime import nowtz
from orchestrator.workflow import ProcessStatus
from test.unit_tests.workflows import assert_complete, assert_state, extract_state, run_workflow


@pytest.fixture
def task():
    three_weeks_ago = nowtz() - timedelta(weeks=3)
    two_weeks_ago = nowtz() - timedelta(weeks=2)
    state = {"foo": "bar"}

    generic_step = ProcessStepTable(name="generic-step", status="success", state=state)

    wf_old = WorkflowTable(
        workflow_id=uuid4(), name="nice and old task", description="nice and old task", target=Target.SYSTEM
    )
    task_old = ProcessTable(
        workflow_id=wf_old.workflow_id,
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=two_weeks_ago,
        steps=[generic_step],
        is_task=True,
    )
    wf_new = WorkflowTable(
        workflow_id=uuid4(), name="nice and new task", description="nice and new task", target=Target.SYSTEM
    )

    task_new = ProcessTable(
        workflow_id=wf_new.workflow_id,
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=nowtz(),
        steps=[generic_step],
        is_task=True,
    )
    wf = WorkflowTable(workflow_id=uuid4(), name="nice process", description="nice process", target=Target.SYSTEM)

    process = ProcessTable(
        workflow_id=wf.workflow_id,
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=two_weeks_ago,
        steps=[generic_step],
        is_task=False,
    )
    db.session.add_all([wf_old, wf_new, wf, generic_step, task_old, task_new, process])
    db.session.commit()


@pytest.mark.workflow
def test_remove_tasks(task):
    result, process, step_log = run_workflow("task_clean_up_tasks", {})
    assert_complete(result)
    res = extract_state(result)
    state = {"process_id": res["process_id"], "reporter": "john.doe", "tasks_removed": 1}
    assert_state(result, state)

    processes = db.session.scalars(select(ProcessTable)).all()

    assert len(processes) == 3
    assert sorted(p.workflow.name for p in processes) == sorted(
        ["nice and new task", "nice process", "task_clean_up_tasks"]
    )

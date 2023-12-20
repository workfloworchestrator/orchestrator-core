from unittest import mock
from uuid import uuid4

import pytest

from orchestrator.config.assignee import Assignee
from orchestrator.db import ProcessStepTable, ProcessTable, WorkflowTable, db
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus
from test.unit_tests.workflows import assert_complete, assert_state, extract_state, run_workflow


@pytest.fixture
def waiting_process():
    state = {"foo": "bar"}
    pid = uuid4()
    workflow_id = uuid4()
    waiting_workflow = WorkflowTable(
        workflow_id=workflow_id, name="Waiting workflow", target=Target.SYSTEM, description="Description"
    )

    process = ProcessTable(
        process_id=pid,
        workflow_id=workflow_id,
        last_status=ProcessStatus.WAITING,
        assignee=Assignee.SYSTEM,
        last_step="waiting-step",
        created_by="Fredje",
    )
    success_step = ProcessStepTable(
        process_id=pid, name="generic-step", status="success", state=state, created_by="Fredje"
    )
    waiting_step = ProcessStepTable(
        process_id=pid, name="waiting-step", status="waiting", state="Uberly cool error message", created_by="Fredje"
    )

    db.session.add_all([waiting_workflow, process, success_step, waiting_step])
    db.session.commit()
    return process


@pytest.mark.workflow
def test_resume_workflow(waiting_process):
    with mock.patch("orchestrator.services.processes.resume_process") as m:
        result, process, step_log = run_workflow("task_resume_workflows", {})
        assert_complete(result)
        #
        res = extract_state(result)
        state = {
            "process_id": res["process_id"],
            "reporter": "john.doe",
            "number_of_waiting_processes": 1,
            "number_of_resumed_process_ids": 1,
            "waiting_process_ids": [str(waiting_process.process_id)],
            "resumed_process_ids": [str(waiting_process.process_id)],
        }
        assert_state(result, state)
        m.assert_called_once()


@pytest.mark.workflow
def test_resume_workflow_non_204(waiting_process):
    with mock.patch("orchestrator.services.processes.resume_process") as m:
        m.side_effect = Exception("Failed to resume")

        result, process, step_log = run_workflow("task_resume_workflows", {})
        assert_complete(result)
        #
        res = extract_state(result)
        state = {
            "process_id": res["process_id"],
            "reporter": "john.doe",
            "number_of_waiting_processes": 1,
            "number_of_resumed_process_ids": 0,
            "waiting_process_ids": [str(waiting_process.process_id)],
            "resumed_process_ids": [],
        }
        assert_state(result, state)
        m.assert_called_once()

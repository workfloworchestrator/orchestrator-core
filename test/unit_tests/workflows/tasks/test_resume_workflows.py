import uuid
from unittest import mock

import pytest

from orchestrator.config.assignee import Assignee
from orchestrator.db import ProcessStepTable, ProcessTable, WorkflowTable, db
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus
from test.unit_tests.workflows import assert_complete, assert_state, extract_state, run_workflow

WORKFLOW_ID = uuid.uuid4()
PID = uuid.uuid4()


@pytest.fixture
def waiting_process():

    state = {"foo": "bar"}

    success_step = ProcessStepTable(pid=PID, name="generic-step", status="success", state=state, created_by="Fredje")
    waiting_step = ProcessStepTable(
        pid=PID, name="waiting-step", status="waiting", state="Uberly cool error message", created_by="Fredje"
    )

    process = ProcessTable(
        pid=PID,
        workflow=WORKFLOW_ID,
        last_status=ProcessStatus.WAITING,
        assignee=Assignee.SYSTEM,
        last_step="waiting-step",
        created_by="Fredje",
    )

    waiting_workflow = WorkflowTable(name="Waiting workflow", target=Target.SYSTEM, description="Description")

    db.session.add(waiting_workflow)
    db.session.add(process)
    db.session.add(success_step)
    db.session.add(waiting_step)
    db.session.commit()


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
            "number_of_resumed_pids": 1,
            "waiting_pids": [str(PID)],
            "resumed_pids": [str(PID)],
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
            "number_of_resumed_pids": 0,
            "waiting_pids": [str(PID)],
            "resumed_pids": [],
        }
        assert_state(result, state)
        m.assert_called_once()

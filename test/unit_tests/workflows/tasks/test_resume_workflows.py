from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select

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


@pytest.fixture
def stuck_created_note_process():
    workflow = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "modify_note"))

    process = ProcessTable(
        process_id=uuid4(),
        workflow_id=workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        assignee=Assignee.SYSTEM,
        last_step="",
        created_by="Fredje",
    )
    db.session.add(process)
    db.session.commit()
    return process


@pytest.fixture
def stuck_resumed_note_workflow():
    state = {"foo": "bar"}
    pid = uuid4()
    workflow = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "modify_note"))

    process = ProcessTable(
        process_id=pid,
        workflow_id=workflow.workflow_id,
        last_status=ProcessStatus.RESUMED,
        assignee=Assignee.SYSTEM,
        last_step="generic-step",
        created_by="Fredje",
    )
    success_step = ProcessStepTable(
        process_id=pid, name="generic-step", status="success", state=state, created_by="Fredje"
    )

    db.session.add_all([process, success_step])
    db.session.commit()
    return process


@pytest.mark.workflow
@mock.patch("orchestrator.services.processes.resume_process")
@mock.patch("orchestrator.services.processes.restart_process")
def test_resume_workflow(
    mock_restart_process, mock_resume_process, waiting_process, stuck_created_note_process, stuck_resumed_note_workflow
):
    result, _, _ = run_workflow("task_resume_workflows", {})
    assert_complete(result)
    #
    res = extract_state(result)
    state = {
        "process_id": res["process_id"],
        "reporter": "john.doe",
        "number_of_waiting_processes": 1,
        "created_processes_stuck": 1,
        "resumed_processes_stuck": 1,
        "waiting_process_ids": [str(waiting_process.process_id)],
        "created_state_process_ids": [str(stuck_created_note_process.process_id)],
        "resumed_state_process_ids": [str(stuck_resumed_note_workflow.process_id)],
        "number_of_resumed_process_ids": 2,
        "number_of_started_process_ids": 1,
    }
    assert_state(result, state)

    assert mock_resume_process.call_count == 2
    assert mock_restart_process.call_count == 1


@mock.patch("orchestrator.services.processes.resume_process")
def test_resume_workflow_non_204(mock_resume_process, waiting_process):
    mock_resume_process.side_effect = Exception("Failed to resume")

    result, _, _ = run_workflow("task_resume_workflows", {})
    assert_complete(result)
    #
    res = extract_state(result)
    state = {
        "process_id": res["process_id"],
        "reporter": "john.doe",
        "number_of_waiting_processes": 1,
        "created_processes_stuck": 0,
        "resumed_processes_stuck": 0,
        "waiting_process_ids": [str(waiting_process.process_id)],
        "created_state_process_ids": [],
        "resumed_state_process_ids": [],
        "number_of_resumed_process_ids": 0,
        "number_of_started_process_ids": 0,
    }
    assert_state(result, state)
    mock_resume_process.assert_called_once()

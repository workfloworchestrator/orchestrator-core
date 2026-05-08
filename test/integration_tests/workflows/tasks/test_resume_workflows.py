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

from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import ProcessStepTable, ProcessTable, WorkflowTable, db
from orchestrator.core.targets import Target
from orchestrator.core.workflow import ProcessStatus
from test.integration_tests.workflows import assert_complete, assert_state, extract_state, run_workflow


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
@mock.patch("orchestrator.core.services.processes.resume_process")
@mock.patch("orchestrator.core.services.processes.restart_process")
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


@mock.patch("orchestrator.core.services.processes.resume_process")
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


@mock.patch("orchestrator.core.services.processes.resume_process")
@mock.patch("orchestrator.core.services.processes.restart_process")
def test_restart_created_workflows_exception(mock_restart_process, mock_resume_process, stuck_created_note_process):
    mock_restart_process.side_effect = Exception("restart failed")

    result, _, _ = run_workflow("task_resume_workflows", {})
    assert_complete(result)

    res = extract_state(result)
    # Process should have been attempted but failed, so not in started list
    assert res["number_of_started_process_ids"] == 0
    assert mock_restart_process.call_count == 1


@mock.patch("orchestrator.core.services.processes.resume_process")
def test_resume_process_not_found(mock_resume_process):
    """When process_id doesn't exist in DB, resume skips it via continue."""
    from orchestrator.core.workflows.tasks.resume_workflows import resume_found_workflows

    nonexistent_id = str(uuid4())
    result = resume_found_workflows(
        {
            "waiting_process_ids": [nonexistent_id],
            "resumed_state_process_ids": [],
        }
    )
    assert result.issuccess()
    state = result.unwrap()
    assert state["number_of_resumed_process_ids"] == 0
    mock_resume_process.assert_not_called()


@mock.patch("orchestrator.core.services.processes.restart_process")
def test_restart_process_not_found(mock_restart_process):
    """When process_id doesn't exist in DB, restart skips it via continue."""
    from orchestrator.core.workflows.tasks.resume_workflows import restart_created_workflows

    nonexistent_id = str(uuid4())
    result = restart_created_workflows({"created_state_process_ids": [nonexistent_id]})
    assert result.issuccess()
    state = result.unwrap()
    assert state["number_of_started_process_ids"] == 0
    mock_restart_process.assert_not_called()

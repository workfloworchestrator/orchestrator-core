from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from orchestrator.db import ProcessTable
from orchestrator.db.models import InputStateTable
from orchestrator.services.executors.threadpool import (
    thread_resume_process,
    thread_start_process,
)
from orchestrator.services.processes import RESUME_WORKFLOW_REMOVED_ERROR_MSG, START_WORKFLOW_REMOVED_ERROR_MSG
from orchestrator.targets import Target
from orchestrator.workflow import (
    ProcessStat,
    ProcessStatus,
    Success,
    make_workflow,
    step,
)


def mock_process_data():
    @step("test step")
    def test_step():
        pass

    wf = make_workflow(lambda: None, "description", None, Target.SYSTEM, [test_step])
    wf.name = "name"

    process_id = uuid4()
    initial_state_dict = {
        "process_id": process_id,
        "reporter": mock.sentinel.user,
        "workflow_name": mock.sentinel.wf_name,
        "workflow_target": Target.SYSTEM,
    }
    initial_state = Success(dict(initial_state_dict))
    mock_update_pstat = MagicMock()
    pstat = ProcessStat(process_id, wf, initial_state, wf.steps, current_user=mock.sentinel.user)
    pstat.update = mock_update_pstat

    process = MagicMock(spec=ProcessTable)
    return pstat, process, wf, mock_update_pstat, initial_state_dict


@mock.patch("orchestrator.services.executors.threadpool.db")
@mock.patch("orchestrator.services.executors.threadpool._get_process")
@mock.patch("orchestrator.services.executors.threadpool.retrieve_input_state")
@mock.patch("orchestrator.services.executors.threadpool._run_process_async")
@mock.patch("orchestrator.services.processes.get_workflow")
def test_thread_start_process(
    mock_get_workflow,
    mock_run_process_async,
    mock_retrieve_input_state,
    mock_get_process,
    mock_db,
):
    pstat, process, wf, mock_update_pstat, initial_state_dict = mock_process_data()

    input_state = {"key": "value"}

    mock_get_workflow.return_value = wf
    mock_get_process.return_value = process
    mock_db.return_value = MagicMock(session=MagicMock())
    mock_retrieve_input_state.return_value = InputStateTable(
        process_id=process.process_id, input_state=input_state, input_type="initial_state"
    )

    expected_updated_state = Success(initial_state_dict | input_state)

    assert process.last_status != ProcessStatus.RUNNING

    thread_start_process(pstat)

    assert process.last_status == ProcessStatus.RUNNING
    mock_retrieve_input_state.assert_called_once_with(mock.ANY, "initial_state")
    mock_update_pstat.assert_called_once_with(state=expected_updated_state)
    mock_run_process_async.assert_called_once()


def test_thread_start_process_errors_workflow_removed(mock_pstat_with_removed_workflow):
    with pytest.raises(ValueError, match=START_WORKFLOW_REMOVED_ERROR_MSG):
        thread_start_process(mock_pstat_with_removed_workflow)


@mock.patch("orchestrator.services.executors.threadpool.db")
@mock.patch("orchestrator.services.executors.threadpool.retrieve_input_state")
@mock.patch("orchestrator.services.executors.threadpool._run_process_async")
@mock.patch("orchestrator.services.executors.threadpool.load_process")
def test_thread_resume_process_suspended(
    mock_load_process,
    mock_run_process_async,
    mock_retrieve_input_state,
    mock_db,
):
    pstat, process, wf, mock_update_pstat, initial_state_dict = mock_process_data()
    process.last_status = ProcessStatus.SUSPENDED
    input_state = {"key": "value"}

    mock_load_process.return_value = pstat
    mock_db.return_value = MagicMock(session=MagicMock())
    mock_retrieve_input_state.return_value = InputStateTable(
        process_id=process.process_id, input_state=input_state, input_type="user_input"
    )

    expected_updated_state = Success(initial_state_dict | input_state)

    assert process.last_status != ProcessStatus.RUNNING

    thread_resume_process(process)

    mock_retrieve_input_state.assert_called_once_with(process.process_id, "user_input")
    mock_update_pstat.assert_called_once_with(state=expected_updated_state)
    mock_run_process_async.assert_called_once()
    assert process.last_status == ProcessStatus.RUNNING


@mock.patch("orchestrator.services.executors.threadpool.db")
@mock.patch("orchestrator.services.executors.threadpool.retrieve_input_state")
@mock.patch("orchestrator.services.executors.threadpool._run_process_async")
@mock.patch("orchestrator.services.executors.threadpool.load_process")
def test_thread_resume_process_failed(
    mock_load_process,
    mock_run_process_async,
    mock_retrieve_input_state,
    mock_db,
):
    pstat, process, _, _, _ = mock_process_data()
    process.last_status = ProcessStatus.FAILED

    mock_load_process.return_value = pstat
    mock_db.return_value = MagicMock(session=MagicMock())

    assert process.last_status != ProcessStatus.RUNNING

    thread_resume_process(process)

    mock_retrieve_input_state.assert_not_called()
    mock_run_process_async.assert_called_once()
    assert process.last_status == ProcessStatus.RUNNING


@mock.patch("orchestrator.services.executors.threadpool.load_process")
def test_thread_resume_process_errors_workflow_removed(mock_load_process, mock_pstat_with_removed_workflow):
    process = MagicMock()
    mock_load_process.return_value = mock_pstat_with_removed_workflow

    with pytest.raises(ValueError, match=RESUME_WORKFLOW_REMOVED_ERROR_MSG):
        thread_resume_process(process)

from unittest import mock
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from orchestrator.db import ProcessTable
from orchestrator.services.executors.threadpool import (
    _set_process_status_running,
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
from orchestrator.workflows.removed_workflow import removed_workflow


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
def test_set_process_status_running(mock_db):
    mock_process = MagicMock()
    mock_process.last_status = ProcessStatus.CREATED

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_process
    mock_db.session.execute.return_value = mock_result

    _set_process_status_running(uuid4())

    assert mock_process.last_status == ProcessStatus.RUNNING
    mock_db.session.commit.assert_called_once()
    mock_db.session.rollback.assert_not_called()


@mock.patch("orchestrator.services.executors.threadpool.db")
def test_set_process_status_running_errors_if_already_running(mock_db):
    mock_process = MagicMock()
    mock_process.last_status = ProcessStatus.RUNNING

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_process
    mock_db.session.execute.return_value = mock_result

    with pytest.raises(Exception, match="Process is already running"):
        _set_process_status_running(uuid4())

    mock_db.session.rollback.assert_called_once()
    mock_db.session.commit.assert_not_called()


@mock.patch("orchestrator.services.executors.threadpool.db")
def test_set_process_status_running_errors_if_not_found(mock_db):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.session.execute.return_value = mock_result

    with pytest.raises(Exception, match="Process is already running"):
        _set_process_status_running(uuid4())

    mock_db.session.rollback.assert_called_once()
    mock_db.session.commit.assert_not_called()


@mock.patch("orchestrator.services.executors.threadpool._set_process_status_running")
@mock.patch("orchestrator.services.executors.threadpool.retrieve_input_state")
@mock.patch("orchestrator.services.executors.threadpool._run_process_async")
def test_thread_start_process(
    mock_run_process_async,
    mock_retrieve_input_state,
    mock_set_process_status_running,
):
    process_id = uuid4()

    pstat = MagicMock()
    pstat.process_id = process_id
    pstat.state.map.return_value = {"state": "test"}

    mock_input_data = MagicMock()
    mock_input_data.input_state = {"key": "val"}
    mock_retrieve_input_state.return_value = mock_input_data
    mock_run_process_async.return_value = process_id

    result = thread_start_process(pstat)

    mock_set_process_status_running.assert_called_once_with(process_id)
    mock_retrieve_input_state.assert_called_once_with(process_id, "initial_state")
    assert pstat.update.call_args_list == [call(state={"state": "test"})]
    mock_run_process_async.assert_called_once()
    assert result == process_id


def test_thread_start_process_erroris_with_removed_workflow():
    pstat = MagicMock()
    pstat.workflow = removed_workflow

    with pytest.raises(ValueError, match=START_WORKFLOW_REMOVED_ERROR_MSG):
        thread_start_process(pstat)


@mock.patch("orchestrator.services.executors.threadpool._set_process_status_running")
@mock.patch("orchestrator.services.executors.threadpool.retrieve_input_state")
@mock.patch("orchestrator.services.executors.threadpool._run_process_async")
@mock.patch("orchestrator.services.executors.threadpool.load_process")
def test_thread_resume_process_resumed(
    mock_load_process,
    mock_run_process_async,
    mock_retrieve_input_state,
    mock_set_process_status_running,
):
    process_id = uuid4()
    process = MagicMock()
    process.process_id = process_id
    process.last_status = ProcessStatus.SUSPENDED

    pstat = MagicMock()
    pstat.process_id = process_id
    pstat.state.map.return_value = {"state": "test"}

    mock_load_process.return_value = pstat

    expected_user = "other user"

    result = thread_resume_process(process, user="other user")

    pstat.user = expected_user
    mock_set_process_status_running.assert_called_once()
    mock_retrieve_input_state.assert_called_once_with(pstat.process_id, "user_input", False)
    assert pstat.update.call_args_list == [call(current_user="other user"), call(state={"state": "test"})]
    mock_run_process_async.assert_called_once()
    assert result == process_id


@mock.patch("orchestrator.services.executors.threadpool.load_process")
def test_thread_resume_process_errors_workflow_removed(mock_load_process):
    pstat = MagicMock(spec=ProcessStat)
    pstat.workflow = removed_workflow

    process = MagicMock()
    process.last_status = "RESUMED"

    mock_load_process.return_value = pstat

    with pytest.raises(ValueError, match=RESUME_WORKFLOW_REMOVED_ERROR_MSG):
        thread_resume_process(process)

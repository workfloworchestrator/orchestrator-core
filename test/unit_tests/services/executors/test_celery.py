from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4, UUID

import pytest
from kombu.exceptions import ConnectionError

from orchestrator.db.models import ProcessTable
from orchestrator.services.executors.celery import (
    _celery_resume_process,
    _celery_set_process_status_resumed,
    _celery_start_process,
)
from orchestrator.services.processes import RESUMABLE_STATUSES
from orchestrator.services.tasks import NEW_TASK, RESUME_WORKFLOW
from orchestrator.workflow import ProcessStatus


@mock.patch("orchestrator.services.tasks.get_celery_task")
@mock.patch("orchestrator.services.executors.celery.get_workflow_by_name")
@mock.patch("orchestrator.services.executors.celery.delete_process")
def test_celery_start_process(mock_delete_process, mock_get_workflow_by_name, mock_get_celery_task):
    pstat = MagicMock()

    trigger_task = MagicMock()
    trigger_task.delay.get.return_value = uuid4()
    mock_get_celery_task.return_value = trigger_task

    process_id = _celery_start_process(pstat)

    assert process_id == pstat.process_id
    mock_get_celery_task.assert_called_once_with(NEW_TASK)
    trigger_task.delay.assert_called_once()
    mock_get_workflow_by_name.assert_called_once()
    mock_delete_process.assert_not_called()


@mock.patch("orchestrator.services.tasks.get_celery_task")
@mock.patch("orchestrator.services.executors.celery.get_workflow_by_name")
@mock.patch("orchestrator.services.executors.celery.delete_process")
def test_celery_start_process_connection_error_should_delete_process(
    mock_delete_process, mock_get_workflow_by_name, mock_get_celery_task
):
    pstat = MagicMock()
    trigger_task = MagicMock()

    def raise_connection_error(x, y):
        raise ConnectionError()

    trigger_task.delay = raise_connection_error
    mock_get_celery_task.return_value = trigger_task

    with pytest.raises(ConnectionError):
        _celery_start_process(pstat)

    mock_delete_process.assert_called_once_with(pstat.process_id)
    mock_get_workflow_by_name.assert_called_once()


@mock.patch("orchestrator.services.tasks.get_celery_task")
@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
def test_celery_resume_process(mock_db, mock_get_celery_task):
    process = MagicMock(spec=ProcessTable)
    process.last_status = ProcessStatus.FAILED
    process.workflow.is_task = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = process
    mock_db.session.execute.return_value = mock_result

    trigger_task = MagicMock()
    trigger_task.delay.get.return_value = uuid4()
    mock_get_celery_task.return_value = trigger_task

    process_id = _celery_resume_process(process)

    assert process_id == process.process_id
    mock_get_celery_task.assert_called_once_with(RESUME_WORKFLOW)
    trigger_task.delay.assert_called_once()
    assert process.last_status == ProcessStatus.RESUMED


@mock.patch("orchestrator.services.executors.celery.set_process_status")
@mock.patch("orchestrator.services.tasks.get_celery_task")
@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
def test_celery_resume_process_connection_error_should_revert_process_status(
    mock_db, mock_get_celery_task, mock_celery_set_process_status
):
    process = MagicMock(spec=ProcessTable)
    process.last_status = ProcessStatus.FAILED
    process.workflow.is_task = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = process
    mock_db.session.execute.return_value = mock_result

    trigger_task = MagicMock()
    trigger_task.delay.side_effect = ConnectionError("network down")
    mock_get_celery_task.return_value = trigger_task

    with pytest.raises(ConnectionError):
        _celery_resume_process(process, user="test")

    mock_celery_set_process_status.assert_called_once_with(process.process_id, ProcessStatus.FAILED)


@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
@pytest.mark.parametrize("status", RESUMABLE_STATUSES)
def test_celery_set_process_status_resumed_valid_statuses(mock_db, status):
    process = MagicMock(spec=ProcessTable)
    process.last_status = status

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = process
    mock_db.session.execute.return_value = mock_result

    _celery_set_process_status_resumed(process)

    assert process.last_status == ProcessStatus.RESUMED
    mock_db.session.commit.assert_called_once()
    mock_db.session.rollback.assert_not_called()


@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
@pytest.mark.parametrize("status", [status for status in ProcessStatus if status not in RESUMABLE_STATUSES])
def test_celery_set_process_status_resumed_invalid_statuses(mock_db, status):
    process = MagicMock(spec=ProcessTable)
    process.last_status = status

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = process
    mock_db.session.execute.return_value = mock_result

    with pytest.raises(Exception, match=f"Process has incorrect status to resume: {status}"):
        _celery_set_process_status_resumed(process)

    assert process.last_status == status
    mock_db.session.commit.assert_not_called()
    mock_db.session.rollback.assert_called_once()

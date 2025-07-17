from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

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
@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
def test_celery_start_process(mock_db, mock_delete_process, mock_get_workflow_by_name, mock_get_celery_task):
    pstat = MagicMock()
    trigger_task = MagicMock()

    delay_result = MagicMock()
    delay_result.get = MagicMock()
    delay_result.get.return_value = uuid4()

    trigger_task.delay.return_value = delay_result
    mock_get_celery_task.return_value = trigger_task

    process_id = _celery_start_process(pstat)

    assert process_id == pstat.process_id
    mock_get_celery_task.assert_called_once_with(NEW_TASK)
    trigger_task.delay.assert_called_once()
    mock_get_workflow_by_name.assert_called_once()


@mock.patch("orchestrator.services.tasks.get_celery_task")
@mock.patch("orchestrator.services.executors.celery.get_workflow_by_name")
@mock.patch("orchestrator.services.executors.celery.delete_process")
@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
def test_celery_start_process_connection_error_should_delete_process(
    mock_db, mock_delete_process, mock_get_workflow_by_name, mock_get_celery_task
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
    process = MagicMock()
    process.last_status = ProcessStatus.FAILED
    process.workflow.is_task = False
    trigger_task = MagicMock()

    delay_result = MagicMock()
    delay_result.get = MagicMock()
    delay_result.get.return_value = uuid4()

    trigger_task.delay.return_value = delay_result
    mock_get_celery_task.return_value = trigger_task

    process_id = _celery_resume_process(process)

    assert process_id == process.process_id
    mock_get_celery_task.assert_called_once_with(RESUME_WORKFLOW)
    trigger_task.delay.assert_called_once()
    assert process.last_status == ProcessStatus.RESUMED


@mock.patch("orchestrator.services.tasks.get_celery_task")
@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
def test_celery_resume_process_connection_error_should_revert_process_status(mock_db, mock_get_celery_task):
    process = MagicMock()
    process.last_status = ProcessStatus.FAILED

    trigger_task = MagicMock()

    def raise_connection_error(x, y):
        raise ConnectionError()

    trigger_task.delay = raise_connection_error

    mock_get_celery_task.return_value = trigger_task

    with pytest.raises(ConnectionError):
        _celery_resume_process(process)

    assert process.last_status == ProcessStatus.FAILED


@mock.patch("orchestrator.services.executors.celery.db", return_value=MagicMock(session=MagicMock()))
@pytest.mark.parametrize(
    "process_status,expected_status",
    [(status, status if status not in RESUMABLE_STATUSES else ProcessStatus.RESUMED) for status in ProcessStatus],
)
def test_celery_set_process_status_resumed_valid_statuses(mock_db, process_status, expected_status):
    process = MagicMock(spec=ProcessTable)
    process.last_status = process_status
    _celery_set_process_status_resumed(process)
    assert process.last_status == expected_status

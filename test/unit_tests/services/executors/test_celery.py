from unittest import mock
from unittest.mock import MagicMock

import pytest

from orchestrator.db.models import ProcessTable
from orchestrator.services.executors.celery import (
    _celery_set_process_status_resumed,
)
from orchestrator.services.processes import RESUMABLE_STATUSES
from orchestrator.workflow import ProcessStatus


def test_celery_start_process_workflow():
    assert 1 == 0


def test_celery_start_process_task():
    assert 1 == 0


def test_celery_start_process_connection_error_should_delete_process():
    assert 1 == 0


def test_celery_start_process_errors_workflow_removed():
    assert 1 == 0


def test_celery_resume_process():
    assert 1 == 0


def test_celery_resume_process_errors_workflow_removed():
    assert 1 == 0


def test_celery_start_process_connection_error_should_revert_process_status():
    assert 1 == 0


@mock.patch("orchestrator.db.db", return_value=MagicMock(session=MagicMock()))
@pytest.mark.parametrize(
    "process_status,expected_status",
    [(status, status if status not in RESUMABLE_STATUSES else ProcessStatus.RESUMED) for status in ProcessStatus],
)
def test_celery_set_process_status_resumed_valid_statuses(mock_db, process_status, expected_status):
    process = MagicMock(spec=ProcessTable)
    process.last_status = process_status
    _celery_set_process_status_resumed(process)
    assert process.last_status == expected_status

"""Tests for retry behavior on transient DB errors in Celery worker tasks.

Verifies that transient database errors (OperationalError) are re-raised so Celery
can retry the task, while non-transient errors are still caught and logged.
Also verifies that initial DB queries are wrapped in a database_scope.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from orchestrator.services.tasks import _worker_resume_process, _worker_start_process


@pytest.fixture
def process_id():
    return uuid4()


@pytest.fixture
def mock_broadcast_func():
    return MagicMock()


class TestWorkerStartProcessRetry:
    """Tests for _worker_start_process retry behavior on transient DB errors."""

    @patch("orchestrator.services.tasks.thread_start_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks.load_process")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_reraises_operational_error_for_retry(
        self, mock_db, mock_get_process, mock_load_process, mock_ensure, mock_thread_start, process_id
    ):
        mock_get_process.side_effect = OperationalError("statement", {}, Exception("SSL SYSCALL error: EOF detected"))

        with pytest.raises(OperationalError):
            _worker_start_process(process_id, user="SYSTEM", broadcast_func=None)

    @patch("orchestrator.services.tasks.thread_start_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks.load_process")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_catches_non_transient_errors(
        self, mock_db, mock_get_process, mock_load_process, mock_ensure, mock_thread_start, process_id
    ):
        mock_get_process.side_effect = ValueError("Process not found")

        result = _worker_start_process(process_id, user="SYSTEM", broadcast_func=None)

        assert result is None

    @patch("orchestrator.services.tasks.thread_start_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks.load_process")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_uses_database_scope(
        self, mock_db, mock_get_process, mock_load_process, mock_ensure, mock_thread_start, process_id
    ):
        mock_process = MagicMock()
        mock_get_process.return_value = mock_process
        mock_pstat = MagicMock()
        mock_load_process.return_value = mock_pstat

        _worker_start_process(process_id, user="SYSTEM", broadcast_func=None)

        mock_db.database_scope.assert_called_once()

    @patch("orchestrator.services.tasks.thread_start_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks.load_process")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_operational_error_during_ensure_status_reraises(
        self, mock_db, mock_get_process, mock_load_process, mock_ensure, mock_thread_start, process_id
    ):
        mock_get_process.return_value = MagicMock()
        mock_load_process.return_value = MagicMock()
        mock_ensure.side_effect = OperationalError("statement", {}, Exception("connection reset"))

        with pytest.raises(OperationalError):
            _worker_start_process(process_id, user="SYSTEM", broadcast_func=None)

    @patch("orchestrator.services.tasks.thread_start_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks.load_process")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_operational_error_during_thread_start_reraises(
        self, mock_db, mock_get_process, mock_load_process, mock_ensure, mock_thread_start, process_id
    ):
        mock_get_process.return_value = MagicMock()
        mock_load_process.return_value = MagicMock()
        mock_thread_start.side_effect = OperationalError("statement", {}, Exception("server closed connection"))

        with pytest.raises(OperationalError):
            _worker_start_process(process_id, user="SYSTEM", broadcast_func=None)

    @patch("orchestrator.services.tasks.thread_start_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks.load_process")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_successful_execution_returns_process_id(
        self, mock_db, mock_get_process, mock_load_process, mock_ensure, mock_thread_start, process_id
    ):
        mock_get_process.return_value = MagicMock()
        mock_load_process.return_value = MagicMock()

        result = _worker_start_process(process_id, user="SYSTEM", broadcast_func=None)

        assert result == process_id


class TestWorkerResumeProcessRetry:
    """Tests for _worker_resume_process retry behavior on transient DB errors."""

    @patch("orchestrator.services.tasks.thread_resume_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_reraises_operational_error_for_retry(
        self, mock_db, mock_get_process, mock_ensure, mock_thread_resume, process_id
    ):
        mock_get_process.side_effect = OperationalError("statement", {}, Exception("SSL SYSCALL error: EOF detected"))

        with pytest.raises(OperationalError):
            _worker_resume_process(process_id, user="SYSTEM", broadcast_func=None)

    @patch("orchestrator.services.tasks.thread_resume_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_catches_non_transient_errors(self, mock_db, mock_get_process, mock_ensure, mock_thread_resume, process_id):
        mock_get_process.side_effect = ValueError("Process not found")

        result = _worker_resume_process(process_id, user="SYSTEM", broadcast_func=None)

        assert result is None

    @patch("orchestrator.services.tasks.thread_resume_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_uses_database_scope(self, mock_db, mock_get_process, mock_ensure, mock_thread_resume, process_id):
        mock_process = MagicMock()
        mock_get_process.return_value = mock_process

        _worker_resume_process(process_id, user="SYSTEM", broadcast_func=None)

        mock_db.database_scope.assert_called_once()

    @patch("orchestrator.services.tasks.thread_resume_process")
    @patch("orchestrator.services.tasks.ensure_correct_process_status")
    @patch("orchestrator.services.tasks._get_process")
    @patch("orchestrator.services.tasks.db")
    def test_successful_execution_returns_process_id(
        self, mock_db, mock_get_process, mock_ensure, mock_thread_resume, process_id
    ):
        mock_get_process.return_value = MagicMock()

        result = _worker_resume_process(process_id, user="SYSTEM", broadcast_func=None)

        assert result == process_id

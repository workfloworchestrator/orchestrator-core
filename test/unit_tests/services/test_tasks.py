from unittest.mock import MagicMock, patch

import pytest

from orchestrator.services.tasks import CeleryJobWorkerStatus


@pytest.fixture
def mock_celery():
    """Create a mock Celery instance."""
    return MagicMock()


def test_celery_job_worker_status_handles_none_from_inspection_api(mock_celery):
    """Test that CeleryJobWorkerStatus handles None returns from Celery inspection API.

    This can happen with prefork worker pool when workers don't respond within timeout.
    Fixes issue #1455.
    """
    # Mock the inspection API to return None (as happens with prefork worker pool)
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = None
    mock_inspect.scheduled.return_value = None
    mock_inspect.reserved.return_value = None
    mock_inspect.active.return_value = None

    mock_celery.control.inspect.return_value = mock_inspect

    # Initialize celery so _celery global is set
    with patch("orchestrator.services.tasks._celery", mock_celery):
        # Should not raise TypeError: object of type 'NoneType' has no len()
        status = CeleryJobWorkerStatus()

        # Verify it handles None gracefully with appropriate defaults
        assert status.number_of_workers_online == 0
        assert status.number_of_queued_jobs == 0
        assert status.number_of_running_jobs == 0
        assert status.executor_type == "celery"


def test_celery_job_worker_status_with_valid_inspection_data(mock_celery):
    """Test that CeleryJobWorkerStatus correctly processes valid inspection data."""
    # Mock the inspection API with valid data
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = {
        "worker1@host": {"total": {}},
        "worker2@host": {"total": {}},
    }
    mock_inspect.scheduled.return_value = {
        "worker1@host": [{"id": "task1"}, {"id": "task2"}],
    }
    mock_inspect.reserved.return_value = {
        "worker1@host": [{"id": "task3"}],
    }
    mock_inspect.active.return_value = {
        "worker1@host": [{"id": "task4"}, {"id": "task5"}],
        "worker2@host": [{"id": "task6"}],
    }

    mock_celery.control.inspect.return_value = mock_inspect

    with patch("orchestrator.services.tasks._celery", mock_celery):
        status = CeleryJobWorkerStatus()

        assert status.number_of_workers_online == 2
        assert status.number_of_queued_jobs == 3  # 2 scheduled + 1 reserved
        assert status.number_of_running_jobs == 3  # 2 active on worker1 + 1 on worker2
        assert status.executor_type == "celery"


def test_celery_job_worker_status_with_mixed_none_and_valid_data(mock_celery):
    """Test that CeleryJobWorkerStatus handles mix of None and valid data."""
    # Mock the inspection API with some None and some valid data
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = {"worker1@host": {"total": {}}}
    mock_inspect.scheduled.return_value = None  # Returns None
    mock_inspect.reserved.return_value = {"worker1@host": [{"id": "task1"}]}
    mock_inspect.active.return_value = None  # Returns None

    mock_celery.control.inspect.return_value = mock_inspect

    with patch("orchestrator.services.tasks._celery", mock_celery):
        status = CeleryJobWorkerStatus()

        assert status.number_of_workers_online == 1
        assert status.number_of_queued_jobs == 1  # 0 scheduled + 1 reserved
        assert status.number_of_running_jobs == 0
        assert status.executor_type == "celery"


def test_celery_job_worker_status_with_empty_dicts(mock_celery):
    """Test that CeleryJobWorkerStatus handles empty dict returns."""
    # Mock the inspection API with empty dicts
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = {}
    mock_inspect.scheduled.return_value = {}
    mock_inspect.reserved.return_value = {}
    mock_inspect.active.return_value = {}

    mock_celery.control.inspect.return_value = mock_inspect

    with patch("orchestrator.services.tasks._celery", mock_celery):
        status = CeleryJobWorkerStatus()

        assert status.number_of_workers_online == 0
        assert status.number_of_queued_jobs == 0
        assert status.number_of_running_jobs == 0
        assert status.executor_type == "celery"


def test_celery_job_worker_status_without_celery_initialized():
    """Test that CeleryJobWorkerStatus handles case when Celery is not initialized."""
    with patch("orchestrator.services.tasks._celery", None):
        with patch("orchestrator.services.tasks.logger") as mock_logger:
            # Should not crash, just log error
            status = CeleryJobWorkerStatus()

            # Verify it creates the object but with default executor_type
            assert status.executor_type == "celery"

            # Verify error was logged
            mock_logger.error.assert_called_once_with("Can't create CeleryJobStatistics. Celery is not initialised.")

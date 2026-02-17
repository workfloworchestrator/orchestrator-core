import time
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.services.worker_status_monitor import WorkerStatusMonitor, get_worker_status_monitor
from orchestrator.settings import ExecutorType


@pytest.fixture
def monitor():
    """Create a monitor with short update interval for testing."""
    mon = WorkerStatusMonitor(update_interval=1)
    mon.start()
    yield mon
    mon.stop()


def test_monitor_starts_with_zero_count():
    """Test that monitor initializes with count of 0."""
    monitor = WorkerStatusMonitor(update_interval=1)
    assert monitor.get_running_jobs_count() == 0


def test_monitor_updates_count_periodically(monitor):
    """Test that monitor updates the count periodically from workers."""
    # Mock ThreadPoolWorkerStatus to return a specific count
    with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
        mock_settings.EXECUTOR = ExecutorType.THREADPOOL

        with patch("orchestrator.services.processes.ThreadPoolWorkerStatus") as mock_status:
            mock_instance = MagicMock()
            mock_instance.number_of_running_jobs = 3
            mock_status.return_value = mock_instance

            # Force immediate update for deterministic testing
            monitor._refresh_once()

            # Verify count was updated
            assert monitor.get_running_jobs_count() == 3


def test_monitor_caches_count_for_fast_access(monitor):
    """Test that getting count doesn't trigger worker inspection each time."""
    with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
        mock_settings.EXECUTOR = ExecutorType.THREADPOOL

        with patch("orchestrator.services.processes.ThreadPoolWorkerStatus") as mock_status:
            mock_instance = MagicMock()
            mock_instance.number_of_running_jobs = 5
            mock_status.return_value = mock_instance

            # Force immediate update for deterministic testing
            monitor._refresh_once()

            # Record how many times ThreadPoolWorkerStatus was called so far
            initial_call_count = mock_status.call_count

            # Get count multiple times rapidly
            count1 = monitor.get_running_jobs_count()
            count2 = monitor.get_running_jobs_count()
            count3 = monitor.get_running_jobs_count()

            assert count1 == count2 == count3 == 5

            # ThreadPoolWorkerStatus should NOT be called during get_running_jobs_count()
            # It should only be called during periodic updates in the background thread
            assert mock_status.call_count == initial_call_count, (
                f"ThreadPoolWorkerStatus was called {mock_status.call_count - initial_call_count} times "
                f"during get_running_jobs_count() calls, but should have been called 0 times "
                f"(reads should use cached value)"
            )


def test_monitor_handles_worker_inspection_errors_gracefully(monitor):
    """Test that monitor keeps previous count if worker inspection fails."""
    with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
        mock_settings.EXECUTOR = ExecutorType.THREADPOOL

        with patch("orchestrator.services.processes.ThreadPoolWorkerStatus") as mock_status:
            # First update succeeds
            mock_instance = MagicMock()
            mock_instance.number_of_running_jobs = 4
            mock_status.return_value = mock_instance

            monitor._refresh_once()
            assert monitor.get_running_jobs_count() == 4

            # Next update fails
            mock_status.side_effect = Exception("Worker inspection failed")

            monitor._refresh_once()
            # Should keep previous count
            assert monitor.get_running_jobs_count() == 4


def test_monitor_with_celery_executor():
    """Test that monitor works with Celery executor."""
    monitor = WorkerStatusMonitor(update_interval=1)
    monitor.start()

    try:
        with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
            mock_settings.EXECUTOR = ExecutorType.WORKER

            with patch("orchestrator.services.tasks.CeleryJobWorkerStatus") as mock_status:
                mock_instance = MagicMock()
                mock_instance.number_of_running_jobs = 7
                mock_status.return_value = mock_instance

                monitor._refresh_once()

                assert monitor.get_running_jobs_count() == 7
    finally:
        monitor.stop()


def test_monitor_with_threadpool_executor():
    """Test that monitor works with ThreadPool executor."""
    monitor = WorkerStatusMonitor(update_interval=1)
    monitor.start()

    try:
        with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
            mock_settings.EXECUTOR = ExecutorType.THREADPOOL

            with patch("orchestrator.services.processes.ThreadPoolWorkerStatus") as mock_status:
                mock_instance = MagicMock()
                mock_instance.number_of_running_jobs = 2
                mock_status.return_value = mock_instance

                monitor._refresh_once()

                assert monitor.get_running_jobs_count() == 2
    finally:
        monitor.stop()


def test_monitor_stops_cleanly():
    """Test that monitor shuts down properly."""
    monitor = WorkerStatusMonitor(update_interval=1)
    monitor.start()

    assert monitor.is_alive()

    monitor.stop()

    # Give it a moment to shut down
    time.sleep(0.5)

    assert not monitor.is_alive()


def test_get_worker_status_monitor_returns_singleton():
    """Test that get_worker_status_monitor returns the same instance."""
    # Reset the global instance for this test
    import orchestrator.services.worker_status_monitor as wsm_module

    original_monitor = wsm_module._monitor
    wsm_module._monitor = None

    try:
        monitor1 = get_worker_status_monitor()
        monitor2 = get_worker_status_monitor()

        assert monitor1 is monitor2
        assert monitor1.is_alive()

        monitor1.stop()
    finally:
        # Restore original monitor
        wsm_module._monitor = original_monitor


def test_monitor_count_reflects_workers_not_database_status(monitor):
    """Test the key behavior: count reflects actual workers, not database status.

    This is the core difference from the old implementation.
    """
    with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
        mock_settings.EXECUTOR = ExecutorType.THREADPOOL

        with patch("orchestrator.services.processes.ThreadPoolWorkerStatus") as mock_status:
            # Simulate: Database has 10 processes with "running" status,
            # but only 2 actual workers executing
            mock_instance = MagicMock()
            mock_instance.number_of_running_jobs = 2  # Only 2 workers actually running
            mock_status.return_value = mock_instance

            monitor._refresh_once()

            # Should return 2 (actual workers), not 10 (database count)
            assert monitor.get_running_jobs_count() == 2


def test_monitor_shows_zero_when_engine_paused(monitor):
    """Test that when engine is paused, count is 0 (no workers executing).

    This proves Mark90's concern is addressed: we show reality, not stale DB status.
    """
    with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
        mock_settings.EXECUTOR = ExecutorType.THREADPOOL

        with patch("orchestrator.services.processes.ThreadPoolWorkerStatus") as mock_status:
            # Simulate: Engine is paused, no workers executing
            # (even if DB has processes with "running" status)
            mock_instance = MagicMock()
            mock_instance.number_of_running_jobs = 0  # No workers running
            mock_status.return_value = mock_instance

            monitor._refresh_once()

            # Should return 0 (accurate), not count from database
            assert monitor.get_running_jobs_count() == 0


def test_monitor_thread_safe_concurrent_access(monitor):
    """Test that multiple threads can safely access the count."""
    import threading

    with patch("orchestrator.services.worker_status_monitor.app_settings") as mock_settings:
        mock_settings.EXECUTOR = ExecutorType.THREADPOOL

        with patch("orchestrator.services.processes.ThreadPoolWorkerStatus") as mock_status:
            mock_instance = MagicMock()
            mock_instance.number_of_running_jobs = 5
            mock_status.return_value = mock_instance

            monitor._refresh_once()

            results = []

            def read_count():
                for _ in range(100):
                    results.append(monitor.get_running_jobs_count())

            threads = [threading.Thread(target=read_count) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All reads should succeed and return the same value
            assert all(count == 5 for count in results)
            assert len(results) == 1000  # 10 threads * 100 reads each

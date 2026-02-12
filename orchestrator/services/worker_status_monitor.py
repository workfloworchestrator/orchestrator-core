# Copyright 2019-2020 GÉANT.
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
import threading

import structlog

from orchestrator.settings import ExecutorType, app_settings

logger = structlog.get_logger(__name__)


class WorkerStatusMonitor(threading.Thread):
    """Background thread that periodically monitors worker status.

    This provides fast access to running process counts without the performance
    penalty of inspecting Celery workers on every API request.
    """

    def __init__(self, update_interval: int = 5, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs, daemon=True)
        self._shutdown_event = threading.Event()
        self.update_interval = update_interval
        self._running_jobs_count = 0
        self._lock = threading.Lock()

    def run(self) -> None:
        logger.info("Starting WorkerStatusMonitor", update_interval=self.update_interval)
        try:
            while not self._shutdown_event.is_set():
                try:
                    count = self._get_worker_count()
                    with self._lock:
                        self._running_jobs_count = count
                except Exception:
                    logger.exception("Failed to update worker status, keeping previous count")

                # Wait for shutdown signal or timeout
                self._shutdown_event.wait(timeout=self.update_interval)

            logger.info("Shutdown WorkerStatusMonitor")
        except Exception:
            logger.exception("Unhandled exception in WorkerStatusMonitor, exiting")

    def _get_worker_count(self) -> int:
        """Get current count of running jobs from workers.

        Raises:
            Exception: If worker status cannot be retrieved
        """
        if app_settings.EXECUTOR == ExecutorType.WORKER:
            from orchestrator.services.tasks import CeleryJobWorkerStatus

            celery_status = CeleryJobWorkerStatus()
            return celery_status.number_of_running_jobs
        from orchestrator.services.processes import ThreadPoolWorkerStatus

        thread_pool_status = ThreadPoolWorkerStatus()
        return thread_pool_status.number_of_running_jobs

    def get_running_jobs_count(self) -> int:
        """Get the cached count of running jobs.

        This is fast as it reads from cache rather than inspecting workers.
        """
        with self._lock:
            return self._running_jobs_count

    def refresh_once(self) -> None:
        """Force an immediate update of the worker count.

        This is primarily for testing to avoid relying on timing/sleep.
        """
        try:
            count = self._get_worker_count()
            with self._lock:
                self._running_jobs_count = count
        except Exception:
            logger.exception("Failed to refresh worker status")

    def stop(self) -> None:
        logger.debug("Sending shutdown signal to WorkerStatusMonitor")
        self._shutdown_event.set()
        self.join(timeout=5)


# Global instance
_monitor: WorkerStatusMonitor | None = None
_monitor_lock = threading.Lock()


def get_worker_status_monitor() -> WorkerStatusMonitor:
    """Get the global WorkerStatusMonitor instance.

    Thread-safe singleton pattern with double-checked locking.
    Restarts the monitor if it was previously stopped.
    """
    global _monitor
    if _monitor is None or not _monitor.is_alive():
        with _monitor_lock:
            # Double-check after acquiring lock
            if _monitor is None or not _monitor.is_alive():
                _monitor = WorkerStatusMonitor(update_interval=app_settings.WORKER_STATUS_INTERVAL)
                _monitor.start()
    return _monitor

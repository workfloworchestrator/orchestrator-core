from typing import Iterable

from prometheus_client import Metric
from prometheus_client.metrics_core import GaugeMetricFamily, StateSetMetricFamily
from prometheus_client.registry import Collector

from orchestrator.schemas.engine_settings import GlobalStatusEnum
from orchestrator.services import settings
from orchestrator.services.worker_status_monitor import get_worker_status_monitor


def _get_engine_status() -> tuple[GlobalStatusEnum, int]:
    """Query for getting the current status of the workflow engine.

    This includes the engine status, and the amount of currently running processes.
    """
    monitor = get_worker_status_monitor()
    running_count = monitor.get_running_jobs_count()

    engine_settings = settings.get_engine_settings()
    engine_status = settings.generate_engine_global_status(engine_settings, running_count)

    return engine_status, running_count


class WorkflowEngineCollector(Collector):
    """Initialize a Prometheus enum and a gauge.

    The enum of the current workflow engine status takes three values:
        - RUNNING
        - PAUSING
        - PAUSED

    This metric also exports the amount of currently running processes.
    """

    def collect(self) -> Iterable[Metric]:
        current_engine_status, running_process_count = _get_engine_status()

        engine_status = StateSetMetricFamily(
            "wfo_engine_status",
            documentation="Current workflow engine status.",
            value={status: status == current_engine_status for status in GlobalStatusEnum.values()},
        )

        engine_process_count = GaugeMetricFamily(
            "wfo_active_process_count",
            unit="count",
            value=running_process_count,
            documentation="Number of currently running processes in the workflow engine.",
        )

        return [engine_status, engine_process_count]

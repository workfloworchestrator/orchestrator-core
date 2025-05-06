from prometheus_client import Enum, Gauge

from orchestrator.schemas.engine_settings import GlobalStatusEnum
from orchestrator.services import settings


def _get_engine_status() -> tuple[GlobalStatusEnum, int]:
    """Query for getting the current status of the workflow engine.

    This includes the engine status, and the amount of currently running processes.
    """
    engine_settings = settings.get_engine_settings()
    engine_status = settings.generate_engine_global_status(engine_settings)

    return engine_status, int(engine_settings.running_processes)


def initialize_engine_status_metrics() -> None:
    """Initialize a Prometheus enum and a gauge.

    The enum of the current workflow engine status takes three values:
        - RUNNING
        - PAUSING
        - PAUSED

    This metric also exports the amount of currently running processes.
    """
    engine_status = Enum(
        "engine_status",
        namespace="wfo",
        states=GlobalStatusEnum.values(),
        documentation="Current workflow engine status.",
    )

    engine_process_count = Gauge(
        "active_process_count",
        namespace="wfo",
        unit="count",
        documentation="Number of currently running processes in the workflow engine.",
    )

    current_engine_status, running_process_count = _get_engine_status()
    engine_status.state(current_engine_status)
    engine_process_count.set(running_process_count)

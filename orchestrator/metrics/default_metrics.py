from orchestrator.metrics.engine import initialize_engine_status_metrics
from orchestrator.metrics.processes import initialize_process_metrics
from orchestrator.metrics.subscriptions import initialize_subscription_count_metrics


def initialize_default_metrics() -> None:
    initialize_subscription_count_metrics()
    initialize_process_metrics()
    initialize_engine_status_metrics()

from orchestrator.metrics.processes import initialize_process_metrics
from orchestrator.metrics.subscriptions import initialize_subscription_count_metrics


def initialize_default_metrics() -> None:
    initialize_subscription_count_metrics()
    initialize_process_metrics()

from prometheus_client import CollectorRegistry

from orchestrator.metrics.engine import WorkflowEngineCollector
from orchestrator.metrics.processes import ProcessCollector
from orchestrator.metrics.subscriptions import SubscriptionCollector

ORCHESTRATOR_METRICS_REGISTRY = CollectorRegistry(auto_describe=True)


def initialize_default_metrics() -> None:
    """Register default Prometheus collectors."""
    ORCHESTRATOR_METRICS_REGISTRY.register(SubscriptionCollector())
    ORCHESTRATOR_METRICS_REGISTRY.register(ProcessCollector())
    ORCHESTRATOR_METRICS_REGISTRY.register(WorkflowEngineCollector())

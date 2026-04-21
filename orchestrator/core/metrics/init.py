from prometheus_client import CollectorRegistry

from orchestrator.core.metrics.engine import WorkflowEngineCollector
from orchestrator.core.metrics.processes import ProcessCollector
from orchestrator.core.metrics.subscriptions import SubscriptionCollector

ORCHESTRATOR_METRICS_REGISTRY = CollectorRegistry(auto_describe=True)


def initialize_default_metrics() -> None:
    """Register default Prometheus collectors."""
    ORCHESTRATOR_METRICS_REGISTRY.register(SubscriptionCollector())
    ORCHESTRATOR_METRICS_REGISTRY.register(ProcessCollector())
    ORCHESTRATOR_METRICS_REGISTRY.register(WorkflowEngineCollector())

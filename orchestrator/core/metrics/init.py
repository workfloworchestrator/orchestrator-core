# Copyright 2019-2026 SURF, GÉANT.
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

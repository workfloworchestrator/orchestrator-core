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

from typing import Iterable

from prometheus_client import Metric
from prometheus_client.registry import Collector

from orchestrator.core.services.flower import get_flower_metrics_subset

FLOWER_METRIC_NAMES = frozenset(
    {
        "flower_worker_online",
        "flower_worker_number_of_currently_executing_tasks",
        "flower_worker_prefetched_tasks",
    }
)


class WorkerCollector(Collector):
    """Re-exposes a subset of Flower's own /metrics as orchestrator-core Prometheus metrics.

    Unlike WorkflowEngineCollector (which derives engine status from worker/queue counts),
    this collector passes through the gauges named in FLOWER_METRIC_NAMES unchanged. It
    yields nothing when FLOWER_URL is unset or Flower is unreachable.
    """

    def collect(self) -> Iterable[Metric]:
        return get_flower_metrics_subset(FLOWER_METRIC_NAMES)

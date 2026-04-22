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
from prometheus_client.metrics_core import GaugeMetricFamily, StateSetMetricFamily
from prometheus_client.registry import Collector

from orchestrator.core.schemas.engine_settings import GlobalStatusEnum
from orchestrator.core.services import settings
from orchestrator.core.services.worker_status_monitor import get_worker_status_monitor


def _get_engine_status() -> tuple[GlobalStatusEnum, int]:
    """Query for getting the current status of the workflow engine.

    This includes the engine status, and the amount of currently running processes.
    """
    monitor = get_worker_status_monitor()
    running_count = monitor.get_running_jobs_count()

    engine_settings = settings.get_engine_settings_table()
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

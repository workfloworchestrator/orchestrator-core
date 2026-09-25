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

import httpx
import structlog
from prometheus_client import Metric
from prometheus_client.parser import text_string_to_metric_families

from orchestrator.core.schemas.engine_settings import WorkerStatus
from orchestrator.core.settings import app_settings

logger = structlog.get_logger(__name__)


def get_flower_metrics() -> str | None:
    """Fetch Flower's own Prometheus exposition text from its /metrics endpoint.

    Returns None (rather than raising) on request failure or when Flower is not
    configured, so callers can render an empty metrics subset instead.
    """
    if not app_settings.FLOWER_URL:
        return None

    try:
        with httpx.Client(base_url=app_settings.FLOWER_URL, timeout=app_settings.FLOWER_REQUEST_TIMEOUT) as client:
            response = client.get("/metrics")
            response.raise_for_status()
            return response.text
    except httpx.HTTPError:
        logger.exception("Failed to fetch metrics from Flower")
        return None


def _filter_metric_families(metrics_text: str, names: Iterable[str]) -> Iterable[Metric]:
    """Raises ValueError if metrics_text is not valid Prometheus exposition text."""
    return [family for family in text_string_to_metric_families(metrics_text) if family.name in names]


def _sum_metric_family(metrics_text: str, name: str) -> int:
    return int(
        sum(sample.value for family in _filter_metric_families(metrics_text, {name}) for sample in family.samples)
    )


def get_flower_worker_status() -> WorkerStatus | None:
    """Derive worker/queue status from Flower's own /metrics endpoint.

    Maps Flower's per-worker gauges onto WorkerStatus: flower_worker_online sums to the
    number of online workers, flower_worker_number_of_currently_executing_tasks to running
    jobs, and flower_worker_prefetched_tasks (accepted by a worker but not yet started) to
    queued jobs.

    Returns None (rather than raising) when Flower is not configured or unreachable, so
    callers can fall back to Celery's inspect() API.
    """
    metrics_text = get_flower_metrics()
    if metrics_text is None:
        return None

    try:
        return WorkerStatus(
            executor_type="celery",
            number_of_workers_online=_sum_metric_family(metrics_text, "flower_worker_online"),
            number_of_queued_jobs=_sum_metric_family(metrics_text, "flower_worker_prefetched_tasks"),
            number_of_running_jobs=_sum_metric_family(
                metrics_text, "flower_worker_number_of_currently_executing_tasks"
            ),
        )
    except ValueError:
        logger.exception("Failed to parse metrics from Flower")
        return None


def get_flower_metrics_subset(flower_metrics_names: Iterable[str]) -> Iterable[Metric]:
    flower_metrics_text = get_flower_metrics()
    if flower_metrics_text is None:
        return []

    try:
        return _filter_metric_families(flower_metrics_text, flower_metrics_names)
    except ValueError:
        logger.exception("Failed to parse metrics from Flower")
        return []

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

"""Tests for orchestrator/core/metrics/workers.py."""

from unittest.mock import patch

from orchestrator.core.metrics.workers import WorkerCollector

FLOWER_METRICS_TEXT = """\
# HELP flower_worker_online Worker online status.
# TYPE flower_worker_online gauge
flower_worker_online{worker="w1@host"} 1.0
# HELP flower_worker_number_of_currently_executing_tasks Number of currently executing tasks.
# TYPE flower_worker_number_of_currently_executing_tasks gauge
flower_worker_number_of_currently_executing_tasks{worker="w1@host"} 2.0
# HELP flower_worker_prefetched_tasks Number of prefetched tasks.
# TYPE flower_worker_prefetched_tasks gauge
flower_worker_prefetched_tasks{task="tasks.new_task",worker="w1@host"} 1.0
# HELP flower_task_prefetch_time_seconds Prefetch time.
# TYPE flower_task_prefetch_time_seconds gauge
flower_task_prefetch_time_seconds{task="tasks.new_task",worker="w1@host"} 0.5
# HELP flower_task_runtime_seconds Task runtime.
# TYPE flower_task_runtime_seconds histogram
flower_task_runtime_seconds_bucket{le="1.0",task="tasks.new_task",worker="w1@host"} 1.0
flower_task_runtime_seconds_bucket{le="+Inf",task="tasks.new_task",worker="w1@host"} 1.0
flower_task_runtime_seconds_sum{task="tasks.new_task",worker="w1@host"} 0.5
flower_task_runtime_seconds_count{task="tasks.new_task",worker="w1@host"} 1.0
# HELP flower_events_total Total events.
# TYPE flower_events_total counter
flower_events_total{task="tasks.new_task",type="task-succeeded",worker="w1@host"} 3.0
"""


def test_worker_collector_returns_nothing_when_flower_unavailable():
    with patch("orchestrator.core.services.flower.get_flower_metrics", return_value=None):
        assert list(WorkerCollector().collect()) == []


def test_worker_collector_only_yields_allowed_worker_gauges():
    with patch("orchestrator.core.services.flower.get_flower_metrics", return_value=FLOWER_METRICS_TEXT):
        families = list(WorkerCollector().collect())

    assert {family.name for family in families} == {
        "flower_worker_online",
        "flower_worker_number_of_currently_executing_tasks",
        "flower_worker_prefetched_tasks",
    }


def test_worker_collector_passes_through_labels_and_values_unchanged():
    with patch("orchestrator.core.services.flower.get_flower_metrics", return_value=FLOWER_METRICS_TEXT):
        families = list(WorkerCollector().collect())

    worker_online = next(family for family in families if family.name == "flower_worker_online")
    assert [(sample.labels, sample.value) for sample in worker_online.samples] == [({"worker": "w1@host"}, 1.0)]

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

"""Tests for orchestrator/core/services/flower.py."""

from unittest.mock import patch

import httpx

from orchestrator.core.services.flower import get_flower_metrics, get_flower_metrics_subset, get_flower_worker_status
from orchestrator.core.settings import app_settings

FLOWER_URL = "http://flower.example:5555"

FLOWER_METRICS_TEXT = """\
# HELP flower_worker_online Worker online status.
# TYPE flower_worker_online gauge
flower_worker_online{worker="worker1@host"} 1.0
flower_worker_online{worker="worker2@host"} 0.0
# HELP flower_worker_number_of_currently_executing_tasks Number of currently executing tasks.
# TYPE flower_worker_number_of_currently_executing_tasks gauge
flower_worker_number_of_currently_executing_tasks{worker="worker1@host"} 2.0
# HELP flower_worker_prefetched_tasks Number of prefetched tasks.
# TYPE flower_worker_prefetched_tasks gauge
flower_worker_prefetched_tasks{task="tasks.new_task",worker="worker1@host"} 1.0
"""


def test_get_flower_worker_status_returns_none_when_metrics_unavailable():
    with patch("orchestrator.core.services.flower.get_flower_metrics", return_value=None):
        assert get_flower_worker_status() is None


def test_get_flower_worker_status_derives_counts_from_metrics():
    with patch("orchestrator.core.services.flower.get_flower_metrics", return_value=FLOWER_METRICS_TEXT):
        status = get_flower_worker_status()

    assert status is not None
    assert status.executor_type == "celery"
    assert status.number_of_workers_online == 1
    assert status.number_of_running_jobs == 2
    assert status.number_of_queued_jobs == 1


def test_get_flower_metrics_disabled_when_url_empty():
    with patch.object(app_settings, "FLOWER_URL", ""):
        assert get_flower_metrics() is None


def test_get_flower_metrics_returns_response_text(httpx_mock):
    body = '# HELP flower_worker_online Worker online status.\nflower_worker_online{worker="w1"} 1.0\n'
    httpx_mock.add_response(url=f"{FLOWER_URL}/metrics", text=body)

    with patch.object(app_settings, "FLOWER_URL", FLOWER_URL):
        assert get_flower_metrics() == body


def test_get_flower_metrics_returns_none_on_request_error(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))

    with patch.object(app_settings, "FLOWER_URL", FLOWER_URL):
        assert get_flower_metrics() is None


def test_get_flower_metrics_returns_none_on_http_error(httpx_mock):
    httpx_mock.add_response(status_code=503)

    with patch.object(app_settings, "FLOWER_URL", FLOWER_URL):
        assert get_flower_metrics() is None


def test_get_flower_worker_status_returns_none_on_malformed_metrics():
    with patch("orchestrator.core.services.flower.get_flower_metrics", return_value="not valid metrics %% {{{"):
        assert get_flower_worker_status() is None


def test_get_flower_metrics_subset_returns_empty_on_malformed_metrics():
    with patch("orchestrator.core.services.flower.get_flower_metrics", return_value="not valid metrics %% {{{"):
        assert list(get_flower_metrics_subset({"flower_worker_online"})) == []

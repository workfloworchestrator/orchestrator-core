# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

from test.integration_tests.metrics.conftest import EMPTY_METRICS


def test_engine_metrics_success(test_client) -> None:
    test_client.put("/api/settings/status", json={"global_lock": True})
    response = test_client.get("api/metrics")
    expected_metric_lines = [
        "# HELP wfo_engine_status Current workflow engine status.",
        "# TYPE wfo_engine_status gauge",
        'wfo_engine_status{wfo_engine_status="PAUSED"} 1.0',
        'wfo_engine_status{wfo_engine_status="PAUSING"} 0.0',
        'wfo_engine_status{wfo_engine_status="RUNNING"} 0.0',
    ]
    assert all(line in response.text for line in expected_metric_lines)

    test_client.put("/api/settings/status", json={"global_lock": False})
    response = test_client.get("/api/metrics")
    assert response.text == EMPTY_METRICS

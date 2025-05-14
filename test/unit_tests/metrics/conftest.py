from http import HTTPStatus

import pytest

EMPTY_METRICS = """# HELP wfo_subscriptions_count Number of subscriptions per product, lifecycle state, customer, and in sync state.
# TYPE wfo_subscriptions_count gauge
# HELP wfo_process_count Number of processes per status, creator, task, product, workflow, customer, and target.
# TYPE wfo_process_count gauge
# HELP wfo_process_seconds_total_count Total time spent on processes in seconds.
# TYPE wfo_process_seconds_total_count gauge
# HELP wfo_engine_status Current workflow engine status.
# TYPE wfo_engine_status gauge
wfo_engine_status{wfo_engine_status="PAUSED"} 0.0
wfo_engine_status{wfo_engine_status="PAUSING"} 0.0
wfo_engine_status{wfo_engine_status="RUNNING"} 1.0
# HELP wfo_active_process_count Number of currently running processes in the workflow engine.
# TYPE wfo_active_process_count gauge
wfo_active_process_count 0.0
"""


@pytest.fixture(autouse=True, scope="function")
def assume_empty_metrics_at_start(test_client) -> None:
    """Assert that at the start of every unit test in this module, the metrics endpoint only contains empty data."""
    response = test_client.get("/api/metrics")
    assert HTTPStatus.OK == response.status_code
    assert response.text == EMPTY_METRICS

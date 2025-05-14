from test.unit_tests.metrics.conftest import EMPTY_METRICS


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

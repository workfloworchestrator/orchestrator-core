from test.unit_tests.conftest import CUSTOMER_ID


def test_process_metrics_success(test_client, mocked_processes) -> None:
    response = test_client.get("api/metrics")
    expected_metric_lines = [
        "# HELP wfo_process_count Number of processes per status, creator, task, product, workflow, customer, and target.",
        "# TYPE wfo_process_count gauge",
        f'wfo_process_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="failed",product_name="Product 2",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 1.0',
        f'wfo_process_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="resumed",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 1.0',
        f'wfo_process_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="completed",product_name="Product 2",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 1.0',
        f'wfo_process_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="suspended",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 1.0',
        f'wfo_process_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="completed",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 1.0',
        f'wfo_process_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="True",last_status="suspended",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 1.0',
        f'wfo_process_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="True",last_status="completed",product_name="Product 2",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 1.0',
        "# HELP wfo_process_seconds_total_count Total time spent on processes in seconds.",
        "# TYPE wfo_process_seconds_total_count gauge",
        f'wfo_process_seconds_total_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="failed",product_name="Product 2",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 600.0',
        f'wfo_process_seconds_total_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="resumed",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 600.0',
        f'wfo_process_seconds_total_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="completed",product_name="Product 2",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 600.0',
        f'wfo_process_seconds_total_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="suspended",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 600.0',
        f'wfo_process_seconds_total_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="False",last_status="completed",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 600.0',
        f'wfo_process_seconds_total_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="True",last_status="suspended",product_name="Product 1",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 600.0',
        f'wfo_process_seconds_total_count{{created_by="None",customer_id="{CUSTOMER_ID}",is_task="True",last_status="completed",product_name="Product 2",workflow_name="workflow_for_testing_processes_py",workflow_target="SYSTEM"}} 600.0',
    ]

    assert all(line in response.text for line in expected_metric_lines)

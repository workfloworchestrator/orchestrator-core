import pytest

from test.unit_tests.workflows import assert_complete, run_workflow


@pytest.mark.workflow
def test_check_subscriptions(generic_subscription_1, generic_subscription_2):
    result, process, step_log = run_workflow("task_validate_products", {})
    assert_complete(result)

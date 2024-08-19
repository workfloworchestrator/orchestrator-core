import pytest
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example2 import Example2
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses, example2_subscription):
    # when

    # TODO: insert mocks here if needed

    result, _, _ = run_workflow("terminate_example2", [{"subscription_id": example2_subscription}, {}])

    # then

    assert_complete(result)
    state = extract_state(result)
    assert "subscription" in state

    # Check subscription in DB

    example2 = Example2.from_subscription(example2_subscription)
    assert example2.end_date is not None
    assert example2.status == SubscriptionLifecycle.TERMINATED

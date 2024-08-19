import pytest
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example4 import Example4
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses, example4_subscription):
    # when

    # TODO: insert mocks here if needed

    result, _, _ = run_workflow("terminate_example4", [{"subscription_id": example4_subscription}, {}])

    # then

    assert_complete(result)
    state = extract_state(result)
    assert "subscription" in state

    # Check subscription in DB

    example4 = Example4.from_subscription(example4_subscription)
    assert example4.end_date is not None
    assert example4.status == SubscriptionLifecycle.TERMINATED

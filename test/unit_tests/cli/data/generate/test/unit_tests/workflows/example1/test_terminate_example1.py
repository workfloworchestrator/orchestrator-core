import pytest
from orchestrator.forms import FormValidationError
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example1 import Example1
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses, example1_subscription):
    # when

    # TODO: insert mocks here if needed

    result, _, _ = run_workflow("terminate_example1", [{"subscription_id": example1_subscription}, {}])

    # then

    assert_complete(result)
    state = extract_state(result)
    assert "subscription" in state

    # Check subscription in DB

    example1 = Example1.from_subscription(example1_subscription)
    assert example1.end_date is not None
    assert example1.status == SubscriptionLifecycle.TERMINATED


@pytest.mark.workflow
def test_can_only_terminate_when_modifiable_boolean_is_true(responses, example1_subscription):
    # given

    # TODO: set test conditions or fixture so that "Add an model_validator that requires some condition(s)" triggers

    # when

    with pytest.raises(FormValidationError) as error:
        result, _, _ = run_workflow("terminate_example1", [{"subscription_id": example1_subscription}, {}])

    # then

    assert error.value.errors[0]["msg"] == "Add an model_validator that requires some condition(s)"

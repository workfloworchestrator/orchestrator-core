import pytest
from orchestrator.forms import FormValidationError
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example1 import Example1
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses, example1_subscription):
    # given

    customer_id = "3f4fc287-0911-e511-80d0-005056956c1a"
    crm = CrmMocks(responses)
    crm.get_customer_by_uuid(customer_id)

    # TODO insert additional mocks, if needed (ImsMocks)

    # when

    init_state = {}

    result, process, step_log = run_workflow(
        "modify_example1",
        [{"subscription_id": example1_subscription}, init_state, {}],
    )

    # then

    assert_complete(result)
    state = extract_state(result)

    example1 = Example1.from_subscription(state["subscription_id"])
    assert example1.status == SubscriptionLifecycle.ACTIVE


@pytest.mark.workflow
def test_must_be_unused_to_change_mode(responses, example1_subscription):
    # given

    # TODO set test conditions or fixture so that "Mode can only be changed when there are no services attached to it" triggers

    # when

    init_state = {}

    with pytest.raises(FormValidationError) as error:
        result, _, _ = run_workflow("modify_example1", [{"subscription_id": example1_subscription}, init_state, {}])

    # then

    assert error.value.errors[0]["msg"] == "Mode can only be changed when there are no services attached to it"


@pytest.mark.workflow
def test_annotated_int_must_be_unique(responses, example1_subscription):
    # given

    # TODO set test conditions or fixture so that "annotated_int must be unique for example1" triggers

    # when

    init_state = {}

    with pytest.raises(FormValidationError) as error:
        result, _, _ = run_workflow("modify_example1", [{"subscription_id": example1_subscription}, init_state, {}])

    # then

    assert error.value.errors[0]["msg"] == "annotated_int must be unique for example1"

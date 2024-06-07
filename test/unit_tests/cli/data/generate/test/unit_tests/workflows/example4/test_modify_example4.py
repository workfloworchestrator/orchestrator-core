import pytest
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example4 import Example4
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow()
def test_happy_flow(responses, example4_subscription):
    # given

    customer_id = "3f4fc287-0911-e511-80d0-005056956c1a"
    crm = CrmMocks(responses)
    crm.get_customer_by_uuid(customer_id)

    # TODO insert additional mocks, if needed (ImsMocks)

    # when

    init_state = {}

    result, process, step_log = run_workflow(
        "modify_example4",
        [{"subscription_id": example4_subscription}, init_state, {}],
    )

    # then

    assert_complete(result)
    state = extract_state(result)

    example4 = Example4.from_subscription(state["subscription_id"])
    assert example4.status == SubscriptionLifecycle.ACTIVE

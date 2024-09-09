import pytest
from orchestrator.db import ProductTable

from products.product_types.example4 import Example4
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses):
    # given

    # TODO insert additional mocks, if needed (ImsMocks)

    product = db.session.scalars(select(ProductTable).where(ProductTable.name == "example4")).one()

    # when

    init_state = {
        "customer_id": customer_id,
        # TODO add initial state
    }

    result, process, step_log = run_workflow("create_example4", [{"product": product.product_id}, init_state])

    # then

    assert_complete(result)
    state = extract_state(result)

    subscription = Example4.from_subscription(state["subscription_id"])
    assert subscription.status == "active"
    assert subscription.description == "TODO add correct description"

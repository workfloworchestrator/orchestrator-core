import pytest
from orchestrator.db import ProductTable
from orchestrator.forms import FormValidationError

from products.product_types.example1 import Example1
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow()
def test_happy_flow(responses):
    # given

    # TODO insert additional mocks, if needed (ImsMocks)

    product = db.session.scalars(select(ProductTable).where(ProductTable.name == "example1")).one()

    # when

    init_state = {
        "customer_id": customer_id,
        # TODO add initial state
    }

    result, process, step_log = run_workflow("create_example1", [{"product": product.product_id}, init_state])

    # then

    assert_complete(result)
    state = extract_state(result)

    subscription = Example1.from_subscription(state["subscription_id"])
    assert subscription.status == "active"
    assert subscription.description == "TODO add correct description"


@pytest.mark.workflow()
def test_must_be_unused_to_change_mode(responses):
    # given

    customer_id = "3f4fc287-0911-e511-80d0-005056956c1a"

    product = db.session.scalars(select(ProductTable).where(ProductTable.name == "example1")).one()

    # TODO set test conditions or fixture so that "Mode can only be changed when there are no services attached to it" triggers

    # when

    init_state = {
        "customer_id": customer_id,
        # TODO add initial state
    }

    with pytest.raises(FormValidationError) as error:
        result, _, _ = run_workflow("create_example1", [{"product": product.product_id}, init_state, {}])

    # then

    assert error.value.errors[0]["msg"] == "Mode can only be changed when there are no services attached to it"


@pytest.mark.workflow()
def test_annotated_int_must_be_unique(responses):
    # given

    customer_id = "3f4fc287-0911-e511-80d0-005056956c1a"

    product = db.session.scalars(select(ProductTable).where(ProductTable.name == "example1")).one()

    # TODO set test conditions or fixture so that "annotated_int must be unique for example1" triggers

    # when

    init_state = {
        "customer_id": customer_id,
        # TODO add initial state
    }

    with pytest.raises(FormValidationError) as error:
        result, _, _ = run_workflow("create_example1", [{"product": product.product_id}, init_state, {}])

    # then

    assert error.value.errors[0]["msg"] == "annotated_int must be unique for example1"

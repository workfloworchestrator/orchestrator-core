from uuid import uuid4

from orchestrator.db import ProductTable, db
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example1 import Example1, Example1Inactive


def test_example1_new():
    product = ProductTable.query.filter(ProductTable.name == "example1").one()

    diff = Example1.diff_product_in_database(product.product_id)
    assert diff == {}

    example1 = Example1Inactive.from_product_id(
        product_id=product.product_id,
        customer_id=uuid4(),
        status=SubscriptionLifecycle.INITIAL,
    )

    assert example1.subscription_id is not None
    assert example1.insync is False

    # TODO: Add more product specific asserts

    assert example1.description == f"Initial subscription of {product.description}"
    example1.save()

    example12 = Example1Inactive.from_subscription(example1.subscription_id)
    assert example1 == example12


def test_example1_load_and_save_db(example1_subscription):
    example1 = Example1.from_subscription(example1_subscription)

    assert example1.insync is True

    # TODO: Add more product specific asserts

    example1.description = "Changed description"

    # TODO: add a product specific change

    example1.save()

    # Explicit commit here as we are not running in the context of a step
    db.session.commit()

    example1 = Example1.from_subscription(example1_subscription)

    # TODO: Add more product specific asserts

    assert example1.description == "Changed description"

from uuid import uuid4

from orchestrator.db import ProductTable, db
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example4 import Example4, Example4Inactive


def test_example4_new():
    product = ProductTable.query.filter(ProductTable.name == "example4").one()

    diff = Example4.diff_product_in_database(product.product_id)
    assert diff == {}

    example4 = Example4Inactive.from_product_id(
        product_id=product.product_id,
        customer_id=uuid4(),
        status=SubscriptionLifecycle.INITIAL,
    )

    assert example4.subscription_id is not None
    assert example4.insync is False

    # TODO: Add more product specific asserts

    assert example4.description == f"Initial subscription of {product.description}"
    example4.save()

    example42 = Example4Inactive.from_subscription(example4.subscription_id)
    assert example4 == example42


def test_example4_load_and_save_db(example4_subscription):
    example4 = Example4.from_subscription(example4_subscription)

    assert example4.insync is True

    # TODO: Add more product specific asserts

    example4.description = "Changed description"

    # TODO: add a product specific change

    example4.save()

    # Explicit commit here as we are not running in the context of a step
    db.session.commit()

    example4 = Example4.from_subscription(example4_subscription)

    # TODO: Add more product specific asserts

    assert example4.description == "Changed description"

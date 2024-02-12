from uuid import uuid4

from orchestrator.db import ProductTable, db
from orchestrator.types import SubscriptionLifecycle

from products.product_types.example2 import Example2, Example2Inactive


def test_example2_new():
    product = ProductTable.query.filter(ProductTable.name == "example2").one()

    diff = Example2.diff_product_in_database(product.product_id)
    assert diff == {}

    example2 = Example2Inactive.from_product_id(
        product_id=product.product_id,
        customer_id=uuid4(),
        status=SubscriptionLifecycle.INITIAL,
    )

    assert example2.subscription_id is not None
    assert example2.insync is False

    # TODO: Add more product specific asserts

    assert example2.description == f"Initial subscription of {product.description}"
    example2.save()

    example22 = Example2Inactive.from_subscription(example2.subscription_id)
    assert example2 == example22


def test_example2_load_and_save_db(example2_subscription):
    example2 = Example2.from_subscription(example2_subscription)

    assert example2.insync is True

    # TODO: Add more product specific asserts

    example2.description = "Changed description"

    # TODO: add a product specific change

    example2.save()

    # Explicit commit here as we are not running in the context of a step
    db.session.commit()

    example2 = Example2.from_subscription(example2_subscription)

    # TODO: Add more product specific asserts

    assert example2.description == "Changed description"

from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.db import db
from orchestrator.types import SubscriptionLifecycle


def test_product_model_with_union_type_directly_below(
    test_union_product,
    test_union_type_product,
    test_product_sub_block_one,
    test_product_block_one,
    sub_one_subscription_1,
):
    UnionProductInactive, _, UnionProduct = test_union_type_product
    SubBlockOneForTestInactive, _, SubBlockOneForTest = test_product_sub_block_one
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    union_subscription_inactive = UnionProductInactive.from_product_id(
        product_id=test_union_product, customer_id=uuid4()
    )

    union_subscription_inactive.test_block = ProductBlockOneForTestInactive.new(
        subscription_id=union_subscription_inactive.subscription_id,
        int_field=3,
        str_field="",
        list_field=[1],
        sub_block=SubBlockOneForTestInactive.new(
            subscription_id=union_subscription_inactive.subscription_id, int_field=3, str_field=""
        ),
        sub_block_2=SubBlockOneForTestInactive.new(
            subscription_id=union_subscription_inactive.subscription_id, int_field=3, str_field=""
        ),
    )

    with pytest.raises(ValidationError) as error:
        UnionProduct.from_other_lifecycle(union_subscription_inactive, SubscriptionLifecycle.ACTIVE)
    assert error.value.errors()[0]["msg"] == "none is not an allowed value"

    new_sub_block = SubBlockOneForTest.new(
        subscription_id=union_subscription_inactive.subscription_id, int_field=1, str_field="2"
    )
    union_subscription_inactive.union_block = new_sub_block
    union_subscription_inactive.save()

    assert union_subscription_inactive.diff_product_in_database(union_subscription_inactive.product.product_id) == {}
    union_subscription = UnionProduct.from_other_lifecycle(union_subscription_inactive, SubscriptionLifecycle.ACTIVE)

    union_subscription.union_block = sub_one_subscription_1.test_block

    with pytest.raises(ValueError) as exc:
        union_subscription.save()
        assert (
            str(exc)
            == "Attempting to save a Foreign `Subscription Instance` directly below a subscription. This is not allowed."
        )


def test_union_product_block_as_sub(
    test_union_sub_product,
    test_union_type_sub_product,
    test_product_block_with_union,
    test_product_type_sub_one,
    sub_one_subscription_1,
):
    UnionProductSubInactive, _, UnionProductSub = test_union_type_sub_product
    UnionProductBlockForTestInactive, _, _ = test_product_block_with_union
    _, _, ProductSubOne = test_product_type_sub_one

    union_subscription_inactive = UnionProductSubInactive.from_product_id(
        product_id=test_union_sub_product, customer_id=uuid4()
    )
    union_subscription_inactive.test_block = UnionProductBlockForTestInactive.new(
        subscription_id=union_subscription_inactive.subscription_id
    )
    union_subscription_inactive.save()

    union_subscription_inactive.test_block.int_field = 1
    union_subscription_inactive.test_block.str_field = "blah"
    union_subscription_inactive.test_block.union_block = sub_one_subscription_1.test_block

    union_subscription_inactive.test_block.list_field = [2]

    union_subscription = UnionProductSub.from_other_lifecycle(
        union_subscription_inactive, status=SubscriptionLifecycle.ACTIVE
    )
    union_subscription.save()

    # This needs to happen in the test due to the fact it is using cached objects.
    db.session.commit()
    assert union_subscription.diff_product_in_database(test_union_sub_product) == {}

    union_subscription_from_database = UnionProductSub.from_subscription(union_subscription.subscription_id)

    assert type(union_subscription_from_database) == type(union_subscription)
    assert union_subscription_from_database.test_block.int_field == union_subscription.test_block.int_field
    assert union_subscription_from_database.test_block.str_field == union_subscription.test_block.str_field
    assert (
        union_subscription_from_database.test_block.union_block.subscription_instance_id
        == sub_one_subscription_1.test_block.subscription_instance_id
    )
    # Do not allow subscriptions that are in use by other subscriptions make an unsafe transition.
    with pytest.raises(ValueError):
        ProductSubOne.from_other_lifecycle(sub_one_subscription_1, SubscriptionLifecycle.TERMINATED)

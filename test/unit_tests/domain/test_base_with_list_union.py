from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.db import db
from orchestrator.types import SubscriptionLifecycle


def test_product_model_with_list_union_type_directly_below(
    test_product_list_union,
    test_product_type_list_union,
    test_product_sub_one,
    test_product_type_sub_one,
    test_product_sub_block_one,
    test_product_block_one,
):
    ProductListUnionInactive, _, ProductListUnion = test_product_type_list_union
    ProductSubOneInactive, _, ProductSubOne = test_product_type_sub_one
    SubBlockOneForTestInactive, _, SubBlockOneForTest = test_product_sub_block_one
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    sub_subscription_inactive = ProductSubOneInactive.from_product_id(
        product_id=test_product_sub_one, customer_id=uuid4()
    )
    sub_subscription_inactive.test_block = SubBlockOneForTestInactive.new(
        subscription_id=sub_subscription_inactive.subscription_id, int_field=1, str_field="blah"
    )
    sub_subscription_inactive.save()
    sub_subscription_active = ProductSubOne.from_other_lifecycle(
        sub_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    sub_subscription_active.save()

    list_union_subscription_inactive = ProductListUnionInactive.from_product_id(
        product_id=test_product_list_union, customer_id=uuid4()
    )

    list_union_subscription_inactive.test_block = ProductBlockOneForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id,
        int_field=3,
        str_field="",
        list_field=[1],
        sub_block=SubBlockOneForTestInactive.new(
            subscription_id=list_union_subscription_inactive.subscription_id, int_field=3, str_field="2"
        ),
        sub_block_2=SubBlockOneForTestInactive.new(
            subscription_id=list_union_subscription_inactive.subscription_id, int_field=3, str_field="2"
        ),
    )

    with pytest.raises(ValidationError):
        ProductListUnion.from_other_lifecycle(list_union_subscription_inactive, SubscriptionLifecycle.ACTIVE)

    new_sub_block = SubBlockOneForTest.new(
        subscription_id=list_union_subscription_inactive.subscription_id, int_field=1, str_field="2"
    )
    list_union_subscription_inactive.list_union_blocks = [new_sub_block]
    list_union_subscription_inactive.save()

    assert (
        list_union_subscription_inactive.diff_product_in_database(list_union_subscription_inactive.product.product_id)
        == {}
    )
    list_union_subscription = ProductListUnion.from_other_lifecycle(
        list_union_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )

    list_union_subscription.list_union_blocks = [sub_subscription_active.test_block]

    with pytest.raises(ValueError) as exc:
        list_union_subscription.save()
        assert (
            str(exc)
            == "Attempting to save a Foreign `Subscription Instance` directly below a subscription. This is not allowed."
        )


def test_list_union_productblock_as_sub(
    test_product_sub_list_union,
    test_product_type_sub_list_union,
    test_product_block_with_list_union,
    test_product_type_sub_one,
    sub_one_subscription_1,
    sub_two_subscription_1,
):
    ProductSubListUnionInactive, _, ProductSubListUnion = test_product_type_sub_list_union
    ProductListUnionBlockForTestInactive, _, _ = test_product_block_with_list_union
    _, _, ProductSubOne = test_product_type_sub_one

    list_union_subscription_inactive = ProductSubListUnionInactive.from_product_id(
        product_id=test_product_sub_list_union, customer_id=uuid4()
    )
    list_union_subscription_inactive.test_block = ProductListUnionBlockForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id
    )
    list_union_subscription_inactive.save()

    list_union_subscription_inactive.test_block.int_field = 1
    list_union_subscription_inactive.test_block.str_field = "blah"
    list_union_subscription_inactive.test_block.list_union_blocks = [
        sub_one_subscription_1.test_block,
        sub_two_subscription_1.test_block,
    ]

    list_union_subscription_inactive.test_block.list_field = [2]

    list_union_subscription = ProductSubListUnion.from_other_lifecycle(
        list_union_subscription_inactive, status=SubscriptionLifecycle.ACTIVE
    )
    list_union_subscription.save()

    # This needs to happen in the test due to the fact it is using cached objects.
    db.session.commit()
    assert list_union_subscription.diff_product_in_database(test_product_sub_list_union) == {}

    union_subscription_from_database = ProductSubListUnion.from_subscription(list_union_subscription.subscription_id)

    assert type(union_subscription_from_database) == type(list_union_subscription)
    assert union_subscription_from_database.test_block.int_field == list_union_subscription.test_block.int_field
    assert union_subscription_from_database.test_block.str_field == list_union_subscription.test_block.str_field

    instance_ids_from_db = [
        block.subscription_instance_id for block in union_subscription_from_database.test_block.list_union_blocks
    ]
    instance_ids_from_subs = [
        sub_one_subscription_1.test_block.subscription_instance_id,
        sub_two_subscription_1.test_block.subscription_instance_id,
    ]
    assert instance_ids_from_db.sort() == instance_ids_from_subs.sort()

    # TODO #1321: uncomment test code below after SAFE_PARENT_TRANSITIONS_FOR_STATUS check has been re-done
    # sub_one_subscription_terminated = ProductSubOne.from_other_lifecycle(
    #     sub_one_subscription_1, SubscriptionLifecycle.TERMINATED
    # )

    # # Do not allow subscriptions that have a parent make an unsafe transition.
    # with pytest.raises(ValueError):
    #     sub_one_subscription_terminated.save()

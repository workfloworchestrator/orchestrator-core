from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.db import db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


def blocks_sorted(blocks):
    def sort_key(block: ProductBlockModel) -> tuple:
        return (block.owner_subscription_id, block.subscription_instance_id)

    return sorted(blocks, key=sort_key, reverse=True)


def test_product_model_with_list_union_type_directly_below(
    test_product_list_union,
    test_product_type_list_union,
    test_product_sub_block_two,
    sub_two_subscription_1,
):
    ProductListUnionInactive, _, ProductListUnion = test_product_type_list_union
    _, _, SubBlockTwoForTest = test_product_sub_block_two

    list_union_subscription_inactive = ProductListUnionInactive.from_product_id(
        product_id=test_product_list_union, customer_id=str(uuid4())
    )

    with pytest.raises(ValidationError):
        ProductListUnion.from_other_lifecycle(list_union_subscription_inactive, SubscriptionLifecycle.ACTIVE)

    new_sub_block_1 = SubBlockTwoForTest.new(
        subscription_id=list_union_subscription_inactive.subscription_id, int_field_2=1
    )
    new_sub_block_2 = SubBlockTwoForTest.new(
        subscription_id=list_union_subscription_inactive.subscription_id, int_field_2=2
    )
    list_union_subscription_inactive.list_union_blocks = [new_sub_block_1, new_sub_block_2]
    list_union_subscription_inactive.save()

    assert (
        list_union_subscription_inactive.diff_product_in_database(list_union_subscription_inactive.product.product_id)
        == {}
    )
    list_union_subscription = ProductListUnion.from_other_lifecycle(
        list_union_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    list_union_subscription.save()

    list_union_sub_from_database = ProductListUnion.from_subscription(list_union_subscription.subscription_id)
    assert type(list_union_sub_from_database) is type(list_union_subscription)

    sorted_db_list = blocks_sorted(list_union_sub_from_database.list_union_blocks)
    sorted_sub_list = blocks_sorted(list_union_subscription.list_union_blocks)
    assert sorted_db_list == sorted_sub_list

    list_union_subscription.list_union_blocks = [sub_two_subscription_1.test_block]

    with pytest.raises(ValueError) as exc:
        list_union_subscription.save()
        assert (
            str(exc)
            == "Attempting to save a Foreign `Subscription Instance` directly below a subscription. This is not allowed."
        )


def test_product_model_with_list_union_type_directly_below_with_relation_overlap(
    test_product_list_union_overlap,
    test_product_type_list_union_overlap,
    test_product_sub_block_one,
    test_product_block_one,
    sub_one_subscription_1,
):
    ProductListUnionInactive, _, ProductListUnion = test_product_type_list_union_overlap
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    list_union_subscription_inactive = ProductListUnionInactive.from_product_id(
        product_id=test_product_list_union_overlap, customer_id=str(uuid4())
    )

    list_union_subscription_inactive.test_block = ProductBlockOneForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id,
        int_field=3,
        str_field="",
        list_field=[1],
        enum_field=DummyEnum.FOO,
        sub_block=SubBlockOneForTestInactive.new(
            subscription_id=list_union_subscription_inactive.subscription_id, int_field=3, str_field="2"
        ),
        sub_block_2=SubBlockOneForTestInactive.new(
            subscription_id=list_union_subscription_inactive.subscription_id, int_field=3, str_field="2"
        ),
    )

    with pytest.raises(ValidationError):
        ProductListUnion.from_other_lifecycle(list_union_subscription_inactive, SubscriptionLifecycle.ACTIVE)

    new_sub_block_1 = SubBlockOneForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id, int_field=11, str_field="111"
    )
    new_sub_block_2 = SubBlockOneForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id, int_field=12, str_field="121"
    )
    list_union_subscription_inactive.list_union_blocks = [new_sub_block_1, new_sub_block_2]
    list_union_subscription_inactive.save()

    assert (
        list_union_subscription_inactive.diff_product_in_database(list_union_subscription_inactive.product.product_id)
        == {}
    )
    list_union_subscription = ProductListUnion.from_other_lifecycle(
        list_union_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    list_union_subscription.save()

    list_union_sub_from_database = ProductListUnion.from_subscription(list_union_subscription.subscription_id)
    assert type(list_union_sub_from_database) is type(list_union_subscription)
    assert list_union_sub_from_database.test_block == list_union_subscription.test_block

    sorted_db_list_len = len(list_union_sub_from_database.list_union_blocks)
    sorted_sub_list_len = len(list_union_subscription.list_union_blocks)
    assert sorted_db_list_len != sorted_sub_list_len
    assert sorted_db_list_len == 5  # 3 were made with test_block, which also get included.

    list_union_subscription.list_union_blocks = [sub_one_subscription_1.test_block]

    with pytest.raises(ValueError) as exc:
        list_union_subscription.save()
        assert (
            str(exc)
            == "Attempting to save a Foreign `Subscription Instance` directly below a subscription. This is not allowed."
        )


def test_list_union_product_block_as_sub(
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
        product_id=test_product_sub_list_union, customer_id=str(uuid4())
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

    list_union_sub_from_database = ProductSubListUnion.from_subscription(list_union_subscription.subscription_id)

    assert type(list_union_sub_from_database) is type(list_union_subscription)
    assert list_union_sub_from_database.test_block.int_field == list_union_subscription.test_block.int_field
    assert list_union_sub_from_database.test_block.str_field == list_union_subscription.test_block.str_field

    sorted_db_list = blocks_sorted(list_union_sub_from_database.test_block.list_union_blocks)
    sorted_sub_list = blocks_sorted(list_union_subscription_inactive.test_block.list_union_blocks)
    assert sorted_db_list == sorted_sub_list

    # Do not allow subscriptions that are in use by other subscriptions make an unsafe transition.
    with pytest.raises(ValueError):
        ProductSubOne.from_other_lifecycle(sub_one_subscription_1, SubscriptionLifecycle.TERMINATED)

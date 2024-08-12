"""Testcases for multiple product block fields with the same type."""

import itertools
from uuid import uuid4

import pytest

from orchestrator.db import db
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


@pytest.fixture
def create_fixtures(test_product_model, test_product_type_one, test_product_block_one, test_product_sub_block_one):

    ProductTypeOneForTestInactive, _, ProductTypeOneForTest = test_product_type_one
    ProductBlockOneForTestInactive, _, _ = test_product_block_one
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one

    customer_id = str(uuid4())

    def create_subblock(subscription, value):
        return SubBlockOneForTestInactive.new(subscription.subscription_id, int_field=value, str_field=str(value))

    value_generator = itertools.count(1000)

    def create_subscription(*, int_value, sub_block_values=None, sub_block_list=None, sub_block1=None, sub_block2=None):
        subscription = ProductTypeOneForTestInactive.from_product_id(
            product_id=test_product_model.product_id, customer_id=customer_id, insync=True
        )

        if sub_block_list:
            # If sub_block1/sub_block2 are passed then use them, otherwise create placeholder subscription blocks with arbitrary values
            sub_block_list = sub_block_list
            sub_block1 = sub_block1 or create_subblock(subscription, next(value_generator))
            sub_block2 = sub_block2 or create_subblock(subscription, next(value_generator))
        else:
            # List stays empty, if sub_block1/sub_block2 are passed use them, otherwise create subscription blocks from sub_block_values
            sub_block_list = []
            sub_block1 = sub_block1 or create_subblock(subscription, sub_block_values[0])
            sub_block2 = sub_block2 or create_subblock(subscription, sub_block_values[1])

        subscription.block = ProductBlockOneForTestInactive.new(
            subscription_id=subscription.subscription_id,
            int_field=int_value,
            str_field=str(int_value),
            sub_block=sub_block1,
            sub_block_2=sub_block2,
            sub_block_list=sub_block_list,
            enum_field=DummyEnum.FOO,
        )
        subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
        subscription.save()
        db.session.commit()
        return subscription

    yield create_subscription, create_subblock


def test_2_field_blocks_from_current_subscription(test_product_type_one, create_fixtures):
    """Test using blocks of the same type in separate fields when the blocks are owned by the current subscription."""
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, _ = create_fixtures

    subscription_10 = create_subscription(int_value=10, sub_block_values=[100, 101])

    subscription_10 = ProductTypeOneForTest.from_subscription(subscription_10.subscription_id)

    assert subscription_10.block.sub_block.int_field == 100
    assert subscription_10.block.sub_block_2.int_field == 101


def test_2_field_blocks_from_current_and_other_subscription(test_product_type_one, create_fixtures):
    """Test using blocks of the same type in separate fields when one block is owned by the current subscription and another block is owned by a different subscription."""
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])

    subscription_10 = create_subscription(
        int_value=10,
        sub_block_values=[300],
        sub_block2=subscription_20.block.sub_block,
    )

    subscription_10 = ProductTypeOneForTest.from_subscription(subscription_10.subscription_id)

    assert subscription_10.block.sub_block.int_field == 300
    assert subscription_10.block.sub_block_2.int_field == 200


def test_2_field_blocks_from_1_other_subscription(test_product_type_one, create_fixtures):
    """Test using blocks of the same type in separate fields when both blocks are owned by 1 different subscription."""
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])

    subscription_10 = create_subscription(
        int_value=10,
        sub_block1=subscription_20.block.sub_block,
        sub_block2=subscription_20.block.sub_block_2,
    )

    subscription_10 = ProductTypeOneForTest.from_subscription(subscription_10.subscription_id)

    assert subscription_10.block.sub_block.int_field == 200
    assert subscription_10.block.sub_block_2.int_field == 201


def test_2_field_identical_blocks_from_1_other_subscription(test_product_type_one, create_fixtures):
    """Test using the exact same block in separate fields when both blocks are owned by 1 different subscription.

    This is incorrect usage and should raise a ValueError.
    """
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])

    with pytest.raises(ValueError, match="Cannot link the same subscription instance multiple times"):
        _ = create_subscription(
            int_value=10,
            sub_block1=subscription_20.block.sub_block,
            sub_block2=subscription_20.block.sub_block,
        )


def test_2_field_blocks_from_2_other_subscriptions(test_product_type_one, create_fixtures):
    """Test using blocks of the same type in separate fields when both blocks are owned by 2 different subscriptions."""
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])
    subscription_21 = create_subscription(int_value=21, sub_block_values=[210, 211])

    subscription_10 = create_subscription(
        int_value=10,
        sub_block1=subscription_20.block.sub_block,
        sub_block2=subscription_21.block.sub_block,
    )

    subscription_10 = ProductTypeOneForTest.from_subscription(subscription_10.subscription_id)

    assert subscription_10.block.sub_block.int_field == 200
    assert subscription_10.block.sub_block_2.int_field == 210


def test_2_field_blocks_from_current_subscription_and_1_list_block_from_other_subscription(
    test_product_type_one, create_fixtures
):
    """Test using blocks of the same type in separate fields when the blocks are owned by the current subscription + 1 block in a list field when the block is owned by a different subscription."""
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])

    subscription_10 = create_subscription(
        int_value=10,
        sub_block_list=[subscription_20.block.sub_block],
    )

    subscription_10 = ProductTypeOneForTest.from_subscription(subscription_10.subscription_id)

    assert subscription_10.block.sub_block_list[0].int_field == 200


def test_2_field_blocks_from_current_subscription_and_2_list_blocks_from_1_other_subscription(
    test_product_type_one, create_fixtures
):
    """Test using blocks of the same type in separate fields when the blocks are owned by the current subscription + 2 blocks in a list field when both blocks are owned by 1 different subscription."""
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])

    subscription_10 = create_subscription(
        int_value=10,
        sub_block_list=[subscription_20.block.sub_block, subscription_20.block.sub_block_2],
    )

    subscription_10 = ProductTypeOneForTest.from_subscription(subscription_10.subscription_id)

    assert subscription_10.block.sub_block_list[0].int_field == 200
    assert subscription_10.block.sub_block_list[1].int_field == 201


def test_2_field_blocks_from_current_subscription_and_2_identical_list_blocks_from_1_other_subscription(
    test_product_type_one, create_fixtures
):
    """Test using blocks of the same type in separate fields when the blocks are owned by the current subscription + 2 identical blocks in a list field when the block are owned by 1 different subscription.

    This is incorrect usage and should raise a ValueError.
    """
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])

    with pytest.raises(ValueError, match="Cannot link the same subscription instance multiple times"):
        _ = create_subscription(
            int_value=10,
            sub_block_list=[subscription_20.block.sub_block, subscription_20.block.sub_block],
        )


def test_2_field_blocks_from_current_subscription_and_2_list_blocks_from_2_other_subscription(
    test_product_type_one, create_fixtures
):
    """Test using blocks of the same type in separate fields when the blocks are owned by the current subscription + 2 blocks in a list field when both blocks are owned by 2 different subscriptions."""
    _, _, ProductTypeOneForTest = test_product_type_one
    create_subscription, create_subblock = create_fixtures

    subscription_20 = create_subscription(int_value=20, sub_block_values=[200, 201])
    subscription_21 = create_subscription(int_value=21, sub_block_values=[210, 211])

    subscription_10 = create_subscription(
        int_value=10,
        sub_block_list=[subscription_20.block.sub_block, subscription_21.block.sub_block],
    )

    subscription_10 = ProductTypeOneForTest.from_subscription(subscription_10.subscription_id)

    assert subscription_10.block.sub_block_list[0].int_field == 200
    assert subscription_10.block.sub_block_list[1].int_field == 210

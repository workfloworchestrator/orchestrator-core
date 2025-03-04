from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from orchestrator.db import SubscriptionTable, db
from orchestrator.domain import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


@pytest.fixture
def create_vertical_subscription(
    test_product_model_nested, test_product_type_one_nested, test_product_block_one_nested
):
    ProductTypeOneNestedForTestInactive, _, _ = test_product_type_one_nested
    ProductBlockOneNestedForTestInactive, _, _ = test_product_block_one_nested

    customer_id = str(uuid4())

    def create(*, size: int, depth: int = 1) -> UUID:
        if depth == size:
            sub_block = None
        else:
            nested_subscription_id = create(size=size, depth=depth + 1)
            nested_subscription = ProductTypeOneNestedForTestInactive.from_subscription(nested_subscription_id)
            sub_block = nested_subscription.block

        subscription = ProductTypeOneNestedForTestInactive.from_product_id(
            product_id=test_product_model_nested.product_id, customer_id=customer_id, insync=True
        )
        subscription.block = ProductBlockOneNestedForTestInactive.new(
            subscription_id=subscription.subscription_id, int_field=depth, sub_block=sub_block
        )
        subscription.save()

        return subscription.subscription_id

    yield create


@pytest.fixture
def create_horizontal_subscription(
    test_product_model, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one
    ProductBlockOneForTestInactive, _, _ = test_product_block_one
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one

    customer_id = str(uuid4())

    def create(*, size: int) -> UUID:
        subscription = ProductTypeOneForTestInactive.from_product_id(
            product_id=test_product_model.product_id, customer_id=customer_id, insync=True
        )

        def create_subblock(value):
            return SubBlockOneForTestInactive.new(subscription.subscription_id, int_field=value, str_field=str(value))

        subscription.block = ProductBlockOneForTestInactive.new(
            subscription_id=subscription.subscription_id,
            int_field=123,
            str_field="abc",
            sub_block=create_subblock(1),
            sub_block_2=create_subblock(2),
            sub_block_list=[create_subblock(n) for n in range(10, 10 + size)],
            enum_field=DummyEnum.FOO,
        )
        subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
        subscription.save()

        return subscription.subscription_id

    yield create


@pytest.fixture
def subscription_with_100_horizontal_blocks(create_horizontal_subscription):
    return create_horizontal_subscription(size=100)


@pytest.mark.benchmark
def test_subscription_model_horizontal_references(
    subscription_with_100_horizontal_blocks, test_product_type_one, monitor_sqlalchemy
):
    # Note: fixtures only execute once per benchmark and are excluded from the measurement

    # given
    _, _, ProductTypeOneForTest = test_product_type_one

    subscription_id = subscription_with_100_horizontal_blocks
    db.session.expunge_all()  # otherwise sqlalchemy will just serve everything from cache

    # when

    with monitor_sqlalchemy():  # Context does nothing unless you set CLI_OPT_MONITOR_SQLALCHEMY
        subscription = ProductTypeOneForTest.from_subscription(subscription_id)

    # then
    assert len(subscription.block.sub_block_list) == 100


@pytest.fixture
def subscription_with_10_vertical_blocks(create_vertical_subscription):
    return create_vertical_subscription(size=10)


@pytest.mark.benchmark
def test_subscription_model_vertical_references(
    subscription_with_10_vertical_blocks, test_product_type_one_nested, monitor_sqlalchemy
):
    # Note: fixtures only execute once per benchmark and are excluded from the measurement

    # given
    _, _, ProductTypeOneNestedForTest = test_product_type_one_nested

    subscription_id = subscription_with_10_vertical_blocks
    db.session.expunge_all()  # otherwise sqlalchemy will just serve everything from cache

    # when

    with monitor_sqlalchemy():  # Context does nothing unless you set CLI_OPT_MONITOR_SQLALCHEMY
        subscription = ProductTypeOneNestedForTest.from_subscription(subscription_id)

    # then
    assert subscription.block is not None
    assert subscription.block.sub_block is not None
    assert subscription.block.sub_block.sub_block is not None
    assert subscription.block.sub_block.sub_block.sub_block is not None
    # no need to check all x levels


@pytest.mark.benchmark
def test_subscription_model_vertical_references_save(create_vertical_subscription, monitor_sqlalchemy):
    # when
    with monitor_sqlalchemy():
        subscription_id = create_vertical_subscription(size=5)

    # then

    # Checks that the subscription was created, without too much overhead
    query_check_created = (
        select(func.count()).select_from(SubscriptionTable).where(SubscriptionTable.subscription_id == subscription_id)
    )
    assert db.session.scalar(query_check_created) == 1


@pytest.mark.benchmark
def test_subscription_model_horizontal_references_save(create_horizontal_subscription, monitor_sqlalchemy):
    # when
    with monitor_sqlalchemy():
        subscription_id = create_horizontal_subscription(size=10)

    # then

    # Checks that the subscription was created, without too much overhead
    query_check_created = (
        select(func.count()).select_from(SubscriptionTable).where(SubscriptionTable.subscription_id == subscription_id)
    )
    assert db.session.scalar(query_check_created) == 1

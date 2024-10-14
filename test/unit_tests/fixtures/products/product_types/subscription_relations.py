from uuid import uuid4

import pytest

from orchestrator.db import db
from orchestrator.db.models import FixedInputTable, ProductTable
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductModel, SubscriptionModel
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_model_list_nested_product_type_one(
    test_product_block_list_nested_db_in_use_by_block, test_product_type_list_nested
):
    product = ProductTable(
        name="TestProductListNestedTypeOne",
        description="Test ProductTable ProductTypeOne",
        product_type="ProductTypeOne",
        tag="TEST",
        status="active",
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="1")

    product_block = test_product_block_list_nested_db_in_use_by_block
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [product_block]

    db.session.add(product)
    db.session.commit()

    _, _, ProductTypeListNestedForTest = test_product_type_list_nested
    SUBSCRIPTION_MODEL_REGISTRY["TestProductListNestedTypeOne"] = ProductTypeListNestedForTest
    yield ProductModel(
        product_id=product.product_id,
        name="TestProductListNestedTypeOne",
        description=product.description,
        product_type=product.product_type,
        tag=product.tag,
        status=ProductLifecycle.ACTIVE,
    )
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductListNestedTypeOne"]


@pytest.fixture
def test_product_model_list_nested_product_type_two(
    test_product_block_list_nested_db_in_use_by_block, test_product_type_list_nested
):
    product = ProductTable(
        name="TestProductListNestedType2",
        description="Test ProductTable ProductTypeTwo",
        product_type="ProductTypeTwo",
        tag="TEST",
        status="active",
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="True")

    product_block = test_product_block_list_nested_db_in_use_by_block
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [product_block]

    db.session.add(product)
    db.session.commit()

    _, _, ProductTypeListNestedForTest = test_product_type_list_nested
    SUBSCRIPTION_MODEL_REGISTRY["TestProductListNestedType2"] = ProductTypeListNestedForTest
    yield ProductModel(
        product_id=product.product_id,
        name="TestProductListNestedType2",
        description=product.description,
        product_type=product.product_type,
        tag=product.tag,
        status=ProductLifecycle.ACTIVE,
    )
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductListNestedType2"]


@pytest.fixture
def factory_subscription_with_nestings_in_use_by(
    test_product_block_list_nested,
    test_product_model_list_nested,
    test_product_type_list_nested,
    test_product_block_list_nested_db_in_use_by_block,
    test_product_model_list_nested_product_type_one,
    test_product_model_list_nested_product_type_two,
):
    """Fixture that creates subscriptions with multiple nestings.

    relations for in use by:
    - subscription_10
        - subscription_20
            - subscription_30
                - subscription_40
                - subscription_41 - terminated
            - subscription_31 - terminated
                - subscription_42
            - subscription_32 - type: ProductTypeOne
                - subscription_40
                - subscription_43

        - subscription_21 - terminated
            - subscription_33
                - subscription_44

        - subscription_22 - type: ProductTypeOne
            - subscription_34 - type: ProductTypeTwo
                - subscription_45

    Returns: dict with subscription ids
    """

    ProductTypeListNestedForTestInactive, _, _ = test_product_type_list_nested
    ProductBlockListNestedForTestInactive, _, _ = test_product_block_list_nested

    customer_id = str(uuid4())

    def create_subscription(*, int_value, sub_blocks=(), different_product_type=None, is_terminated=False):
        product_id = test_product_model_list_nested.product_id
        if different_product_type:
            product_id = different_product_type.product_id

        subscription = ProductTypeListNestedForTestInactive.from_product_id(
            product_id=product_id, customer_id=customer_id, insync=True
        )
        subscription.block = ProductBlockListNestedForTestInactive.new(
            subscription_id=subscription.subscription_id, int_field=int_value, sub_block_list=list(sub_blocks)
        )

        subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
        if is_terminated:
            subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.TERMINATED)

        subscription.save()
        db.session.commit()
        return subscription

    subscription_10 = create_subscription(int_value=10)

    subscription_20 = create_subscription(int_value=20, sub_blocks=[subscription_10.block])
    subscription_21 = create_subscription(int_value=21, sub_blocks=[subscription_10.block], is_terminated=True)
    subscription_22 = create_subscription(
        int_value=22,
        sub_blocks=[subscription_10.block],
        different_product_type=test_product_model_list_nested_product_type_one,
    )

    subscription_30 = create_subscription(int_value=30, sub_blocks=[subscription_20.block])
    subscription_31 = create_subscription(int_value=31, sub_blocks=[subscription_20.block], is_terminated=True)
    subscription_32 = create_subscription(
        int_value=32,
        sub_blocks=[subscription_20.block],
        different_product_type=test_product_model_list_nested_product_type_one,
    )
    subscription_33 = create_subscription(int_value=33, sub_blocks=[subscription_21.block])
    subscription_34 = create_subscription(
        int_value=34,
        sub_blocks=[subscription_22.block],
        different_product_type=test_product_model_list_nested_product_type_two,
    )

    subscription_40 = create_subscription(int_value=40, sub_blocks=[subscription_30.block, subscription_32.block])
    subscription_41 = create_subscription(int_value=41, sub_blocks=[subscription_30.block], is_terminated=True)
    subscription_42 = create_subscription(int_value=42, sub_blocks=[subscription_31.block])
    subscription_43 = create_subscription(int_value=43, sub_blocks=[subscription_32.block])
    subscription_44 = create_subscription(int_value=44, sub_blocks=[subscription_33.block])
    subscription_45 = create_subscription(int_value=45, sub_blocks=[subscription_34.block])

    return {
        "subscription_10": subscription_10.subscription_id,
        "subscription_20": subscription_20.subscription_id,
        "subscription_21": subscription_21.subscription_id,
        "subscription_22": subscription_22.subscription_id,
        "subscription_30": subscription_30.subscription_id,
        "subscription_31": subscription_31.subscription_id,
        "subscription_32": subscription_32.subscription_id,
        "subscription_33": subscription_33.subscription_id,
        "subscription_34": subscription_34.subscription_id,
        "subscription_40": subscription_40.subscription_id,
        "subscription_41": subscription_41.subscription_id,
        "subscription_42": subscription_42.subscription_id,
        "subscription_43": subscription_43.subscription_id,
        "subscription_44": subscription_44.subscription_id,
        "subscription_45": subscription_45.subscription_id,
    }


@pytest.fixture
def factory_subscription_with_nestings_depends_on(
    test_product_block_list_nested,
    test_product_model_list_nested,
    test_product_type_list_nested,
    test_product_block_list_nested_db_in_use_by_block,
    test_product_model_list_nested_product_type_one,
    test_product_model_list_nested_product_type_two,
):
    """Fixture that creates subscriptions with multiple nestings.

    relations for depends on (default product type `Test`):
    - subscription_40
        - subscription_30
            - subscription_20
                - subscription_10
                - subscription_11 - terminated
            - subscription_21 - terminated
                - subscription_12
            - subscription_22 - type: ProductTypeOne
                - subscription_10
                - subscription_13

        - subscription_31 - terminated
            - subscription_23
                - subscription_14

        - subscription_32 - type: ProductTypeOne
            - subscription_24 - type: ProductTypeTwo
                - subscription_15

    Returns: dict with subscription ids
    """
    ProductTypeListNestedForTestInactive, _, _ = test_product_type_list_nested
    ProductBlockListNestedForTestInactive, _, _ = test_product_block_list_nested

    customer_id = str(uuid4())

    def create_subscription(*, int_value, sub_blocks=(), different_product_type=None, is_terminated=False):
        product_id = test_product_model_list_nested.product_id
        if different_product_type:
            product_id = different_product_type.product_id

        subscription = ProductTypeListNestedForTestInactive.from_product_id(
            product_id=product_id, customer_id=customer_id, insync=True
        )
        subscription.block = ProductBlockListNestedForTestInactive.new(
            subscription_id=subscription.subscription_id, int_field=int_value, sub_block_list=list(sub_blocks)
        )

        subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
        if is_terminated:
            subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.TERMINATED)

        subscription.save()
        db.session.commit()
        return subscription

    subscription_10 = create_subscription(int_value=10)
    subscription_11 = create_subscription(int_value=11, is_terminated=True)
    subscription_12 = create_subscription(int_value=12)
    subscription_13 = create_subscription(int_value=13)
    subscription_14 = create_subscription(int_value=14)
    subscription_15 = create_subscription(int_value=15)

    subscription_20 = create_subscription(int_value=20, sub_blocks=[subscription_10.block, subscription_11.block])
    subscription_21 = create_subscription(int_value=21, sub_blocks=[subscription_12.block], is_terminated=True)
    subscription_22 = create_subscription(
        int_value=22,
        sub_blocks=[subscription_10.block, subscription_13.block],
        different_product_type=test_product_model_list_nested_product_type_one,
    )
    subscription_23 = create_subscription(int_value=23, sub_blocks=[subscription_14.block])
    subscription_24 = create_subscription(
        int_value=24,
        sub_blocks=[subscription_15.block],
        different_product_type=test_product_model_list_nested_product_type_two,
    )

    subscription_30 = create_subscription(
        int_value=30, sub_blocks=[subscription_20.block, subscription_21.block, subscription_22.block]
    )
    subscription_31 = create_subscription(int_value=31, sub_blocks=[subscription_23.block], is_terminated=True)
    subscription_32 = create_subscription(
        int_value=32,
        sub_blocks=[subscription_24.block],
        different_product_type=test_product_model_list_nested_product_type_one,
    )

    # create subscription 40 that use subscription 30, 31 and 32
    subscription_40 = create_subscription(
        int_value=40, sub_blocks=[subscription_30.block, subscription_31.block, subscription_32.block]
    )

    return {
        "subscription_10": subscription_10.subscription_id,
        "subscription_11": subscription_11.subscription_id,
        "subscription_12": subscription_12.subscription_id,
        "subscription_13": subscription_13.subscription_id,
        "subscription_14": subscription_14.subscription_id,
        "subscription_15": subscription_15.subscription_id,
        "subscription_20": subscription_20.subscription_id,
        "subscription_21": subscription_21.subscription_id,
        "subscription_22": subscription_22.subscription_id,
        "subscription_23": subscription_23.subscription_id,
        "subscription_24": subscription_24.subscription_id,
        "subscription_30": subscription_30.subscription_id,
        "subscription_31": subscription_31.subscription_id,
        "subscription_32": subscription_32.subscription_id,
        "subscription_40": subscription_40.subscription_id,
    }

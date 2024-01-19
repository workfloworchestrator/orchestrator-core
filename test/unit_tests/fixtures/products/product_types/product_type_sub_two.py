from uuid import uuid4

import pytest

from orchestrator.db import ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_type_sub_two(test_product_sub_block_two):
    SubBlockTwoForTestInactive, SubBlockTwoForTestProvisioning, SubBlockTwoForTest = test_product_sub_block_two

    class ProductSubTwoInactive(SubscriptionModel, is_base=True):
        test_block: SubBlockTwoForTestInactive | None

    class ProductSubTwoProvisioning(ProductSubTwoInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: SubBlockTwoForTestProvisioning

    class ProductSubTwo(ProductSubTwoProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: SubBlockTwoForTest

    SUBSCRIPTION_MODEL_REGISTRY["ProductSubTwo"] = ProductSubTwo
    yield ProductSubTwoInactive, ProductSubTwoProvisioning, ProductSubTwo
    del SUBSCRIPTION_MODEL_REGISTRY["ProductSubTwo"]


@pytest.fixture
def test_product_sub_two(test_product_sub_block_two_db):
    product = ProductTable(
        name="ProductSubTwo", description="Test ProductSubTwo", product_type="Test", tag="Sub", status="active"
    )

    product.product_blocks = [test_product_sub_block_two_db]
    db.session.add(product)
    db.session.commit()
    return product.product_id


@pytest.fixture
def sub_two_subscription_1(test_product_type_sub_two, test_product_sub_block_two, test_product_sub_two):
    ProductSubTwoInactive, _, ProductSubTwo = test_product_type_sub_two
    SubBlockTwoForTestInactive, _, _ = test_product_sub_block_two

    sub_two_subscription_inactive = ProductSubTwoInactive.from_product_id(
        product_id=test_product_sub_two, customer_id=str(uuid4())
    )
    sub_two_subscription_inactive.test_block = SubBlockTwoForTestInactive.new(
        subscription_id=sub_two_subscription_inactive.subscription_id, int_field_2=3
    )
    sub_two_subscription_inactive.save()
    sub_two_subscription_active = ProductSubTwo.from_other_lifecycle(
        sub_two_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    sub_two_subscription_active.save()
    return sub_two_subscription_active

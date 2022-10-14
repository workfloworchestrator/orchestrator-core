from typing import Optional
from uuid import uuid4

import pytest

from orchestrator.db import ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_type_sub_one(test_product_sub_block_one):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one

    class ProductSubOneInactive(SubscriptionModel, is_base=True):
        test_block: Optional[SubBlockOneForTestInactive]

    class ProductSubOneProvisioning(ProductSubOneInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: SubBlockOneForTestProvisioning

    class ProductSubOne(ProductSubOneProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: SubBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["ProductSubOne"] = ProductSubOne
    yield ProductSubOneInactive, ProductSubOneProvisioning, ProductSubOne
    del SUBSCRIPTION_MODEL_REGISTRY["ProductSubOne"]


@pytest.fixture
def test_product_sub_one(test_product_sub_block_one_db):
    product = ProductTable(
        name="ProductSubOne", description="Test ProductSubOne", product_type="Test", tag="Sub", status="active"
    )

    product.product_blocks = [test_product_sub_block_one_db]
    db.session.add(product)
    db.session.commit()
    return product.product_id


@pytest.fixture
def sub_one_subscription_1(test_product_type_sub_one, test_product_sub_block_one, test_product_sub_one):
    ProductSubOneInactive, _, ProductSubOne = test_product_type_sub_one
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one

    sub_one_subscription_inactive = ProductSubOneInactive.from_product_id(
        product_id=test_product_sub_one, customer_id=uuid4()
    )
    sub_one_subscription_inactive.test_block = SubBlockOneForTestInactive.new(
        subscription_id=sub_one_subscription_inactive.subscription_id, int_field=1, str_field="blah"
    )
    sub_one_subscription_inactive.save()
    sub_one_subscription_active = ProductSubOne.from_other_lifecycle(
        sub_one_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    sub_one_subscription_active.save()
    return sub_one_subscription_active

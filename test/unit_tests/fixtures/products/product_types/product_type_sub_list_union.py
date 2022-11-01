from typing import Optional
from uuid import uuid4

import pytest

from orchestrator.db import ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_type_sub_list_union(test_product_block_with_list_union):
    (
        ProductBlockWithListUnionForTestInactive,
        ProductBlockWithListUnionForTestProvisioning,
        ProductBlockWithListUnionForTest,
    ) = test_product_block_with_list_union

    class ProductSubListUnionInactive(SubscriptionModel, is_base=True):
        test_block: Optional[ProductBlockWithListUnionForTestInactive]

    class ProductSubListUnionProvisioning(ProductSubListUnionInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockWithListUnionForTestProvisioning

    class ProductSubListUnion(ProductSubListUnionProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockWithListUnionForTest

    SUBSCRIPTION_MODEL_REGISTRY["ProductSubListUnion"] = ProductSubListUnion
    yield ProductSubListUnionInactive, ProductSubListUnionProvisioning, ProductSubListUnion
    del SUBSCRIPTION_MODEL_REGISTRY["ProductSubListUnion"]


@pytest.fixture
def test_product_sub_list_union(test_product_block_with_list_union_db):
    product = ProductTable(
        name="ProductSubListUnion",
        description="Product with Union sub product_block",
        tag="UnionSub",
        product_type="Test",
        status="active",
    )
    product_block, _, _ = test_product_block_with_list_union_db
    product.product_blocks = [product_block]
    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def product_sub_list_union_subscription_1(
    test_product_sub_list_union,
    test_product_type_sub_list_union,
    test_product_block_with_list_union,
    sub_one_subscription_1,
    sub_two_subscription_1,
):
    ProductSubListUnionInactive, _, ProductSubListUnion = test_product_type_sub_list_union
    ProductListUnionBlockForTestInactive, _, _ = test_product_block_with_list_union

    model = ProductSubListUnionInactive.from_product_id(
        product_id=test_product_sub_list_union,
        customer_id=uuid4(),
        status=SubscriptionLifecycle.INITIAL,
        insync=True,
        description="product sub list union sub description",
    )
    model.test_block = ProductListUnionBlockForTestInactive.new(subscription_id=model.subscription_id)
    model.test_block.int_field = 1
    model.test_block.str_field = "blah"
    model.test_block.list_field = [2]
    model.test_block.list_union_blocks = [
        sub_one_subscription_1.test_block,
        sub_two_subscription_1.test_block,
    ]

    model = ProductSubListUnion.from_other_lifecycle(model, status=SubscriptionLifecycle.ACTIVE)
    model.save()

    db.session.commit()

    return model.subscription_id

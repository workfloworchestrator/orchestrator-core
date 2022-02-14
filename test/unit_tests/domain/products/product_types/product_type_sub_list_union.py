from typing import Optional

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

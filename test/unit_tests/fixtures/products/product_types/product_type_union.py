from typing import Optional, Union

import pytest

from orchestrator.db import ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_union_type_product(test_product_block_one, test_product_sub_block_one):
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one

    class UnionProductInactive(SubscriptionModel, is_base=True):
        test_block: Optional[ProductBlockOneForTestInactive]
        union_block: Optional[Union[ProductBlockOneForTestInactive, SubBlockOneForTestInactive]]

    class UnionProductProvisioning(UnionProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockOneForTestProvisioning
        union_block: Union[ProductBlockOneForTestProvisioning, SubBlockOneForTestProvisioning]

    class UnionProduct(UnionProductProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockOneForTest
        union_block: Union[ProductBlockOneForTest, SubBlockOneForTest]

    SUBSCRIPTION_MODEL_REGISTRY["UnionProduct"] = UnionProduct
    yield UnionProductInactive, UnionProductProvisioning, UnionProduct
    del SUBSCRIPTION_MODEL_REGISTRY["UnionProduct"]


@pytest.fixture
def test_union_product(test_product_block_one_db):
    product = ProductTable(
        name="UnionProduct", description="Test Union Product", product_type="Test", tag="Union", status="active"
    )

    product_block, product_sub_block = test_product_block_one_db
    product.product_blocks = [product_block, product_sub_block]
    db.session.add(product)
    db.session.commit()
    return product.product_id

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
        test_block: ProductBlockOneForTestInactive | None
        union_block: ProductBlockOneForTestInactive | SubBlockOneForTestInactive | None

    class UnionProductProvisioning(UnionProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockOneForTestProvisioning
        union_block: ProductBlockOneForTestProvisioning | SubBlockOneForTestProvisioning

    class UnionProduct(UnionProductProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockOneForTest
        union_block: ProductBlockOneForTest | SubBlockOneForTest

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

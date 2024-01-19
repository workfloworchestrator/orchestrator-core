import pytest

from orchestrator.db import ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_union_type_sub_product(test_product_block_with_union):
    (
        ProductBlockWithUnionForTestInactive,
        ProductBlockWithUnionForTestProvisioning,
        ProductBlockWithUnionForTest,
    ) = test_product_block_with_union

    class UnionProductSubInactive(SubscriptionModel, is_base=True):
        test_block: ProductBlockWithUnionForTestInactive | None

    class UnionProductSubProvisioning(UnionProductSubInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockWithUnionForTestProvisioning

    class UnionProductSub(UnionProductSubProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockWithUnionForTest

    SUBSCRIPTION_MODEL_REGISTRY["UnionProductSub"] = UnionProductSub
    yield UnionProductSubInactive, UnionProductSubProvisioning, UnionProductSub
    del SUBSCRIPTION_MODEL_REGISTRY["UnionProductSub"]


@pytest.fixture
def test_union_sub_product(test_product_block_with_union_db):
    product = ProductTable(
        name="UnionProductSub",
        description="Product with Union sub product_block",
        tag="UnionSub",
        product_type="Test",
        status="active",
    )
    _, _, product_union_sub_block = test_product_block_with_union_db
    product.product_blocks = [product_union_sub_block]
    db.session.add(product)
    db.session.commit()

    return product.product_id

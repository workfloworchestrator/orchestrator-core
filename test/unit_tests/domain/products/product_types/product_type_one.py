import pytest

from orchestrator.db import FixedInputTable, ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductModel, SubscriptionModel
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_type_one(test_product_block_one):
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one

    class ProductTypeOneForTestInactive(SubscriptionModel, is_base=True):
        test_fixed_input: bool
        block: ProductBlockOneForTestInactive

    class ProductTypeOneForTestProvisioning(
        ProductTypeOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        test_fixed_input: bool
        block: ProductBlockOneForTestProvisioning

    class ProductTypeOneForTest(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTest
    yield ProductTypeOneForTestInactive, ProductTypeOneForTestProvisioning, ProductTypeOneForTest
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"]


@pytest.fixture
def test_product_one(test_product_block_one_db):
    product = ProductTable(
        name="TestProductOne", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    product_block, _ = test_product_block_one_db
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [product_block]

    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def test_product_model(test_product_one):
    return ProductModel(
        product_id=test_product_one,
        name="TestProductOne",
        description="Test ProductTable",
        product_type="Test",
        tag="TEST",
        status=ProductLifecycle.ACTIVE,
    )

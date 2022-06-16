import pytest

from orchestrator.db import FixedInputTable, ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductModel, SubscriptionModel
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_one_nested import (
    ProductBlockOneNestedForTest,
    ProductBlockOneNestedForTestInactive,
    ProductBlockOneNestedForTestProvisioning,
)


@pytest.fixture
def test_product_type_one_nested():
    class ProductTypeOneNestedForTestInactive(SubscriptionModel, is_base=True):
        test_fixed_input: bool
        block: ProductBlockOneNestedForTestInactive

    class ProductTypeOneNestedForTestProvisioning(
        ProductTypeOneNestedForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        test_fixed_input: bool
        block: ProductBlockOneNestedForTestProvisioning

    class ProductTypeOneNestedForTest(
        ProductTypeOneNestedForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        test_fixed_input: bool
        block: ProductBlockOneNestedForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOneNested"] = ProductTypeOneNestedForTest
    yield ProductTypeOneNestedForTestInactive, ProductTypeOneNestedForTestProvisioning, ProductTypeOneNestedForTest
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductOneNested"]


@pytest.fixture
def test_product_one_nested(test_product_block_one_nested_db_in_use_by_block):
    product = ProductTable(
        name="TestProductOneNested", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    product_block = test_product_block_one_nested_db_in_use_by_block
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [product_block]

    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def test_product_model_nested(test_product_one_nested):
    return ProductModel(
        product_id=test_product_one_nested,
        name="TestProductOneNested",
        description="Test ProductTable",
        product_type="Test",
        tag="TEST",
        status=ProductLifecycle.ACTIVE,
    )

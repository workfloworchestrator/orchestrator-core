import pytest

from orchestrator.db import FixedInputTable, ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductModel, SubscriptionModel
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_type_list_nested(test_product_block_list_nested):
    ProductBlockListNestedForTestInactive, ProductBlockListNestedForTestProvisioning, ProductBlockListNestedForTest = (
        test_product_block_list_nested
    )

    class ProductTypeListNestedForTestInactive(SubscriptionModel, is_base=True):
        test_fixed_input: bool
        block: ProductBlockListNestedForTestInactive

    class ProductTypeListNestedForTestProvisioning(
        ProductTypeListNestedForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        test_fixed_input: bool
        block: ProductBlockListNestedForTestProvisioning

    class ProductTypeListNestedForTest(
        ProductTypeListNestedForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        test_fixed_input: bool
        block: ProductBlockListNestedForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductListNested"] = ProductTypeListNestedForTest
    yield ProductTypeListNestedForTestInactive, ProductTypeListNestedForTestProvisioning, ProductTypeListNestedForTest
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductListNested"]


@pytest.fixture
def test_product_list_nested(test_product_block_list_nested_db_in_use_by_block):
    product = ProductTable(
        name="TestProductListNested", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    product_block = test_product_block_list_nested_db_in_use_by_block
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [product_block]

    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def test_product_model_list_nested(test_product_list_nested):
    return ProductModel(
        product_id=test_product_list_nested,
        name="TestProductListNested",
        description="Test ProductTable",
        product_type="Test",
        tag="TEST",
        status=ProductLifecycle.ACTIVE,
    )

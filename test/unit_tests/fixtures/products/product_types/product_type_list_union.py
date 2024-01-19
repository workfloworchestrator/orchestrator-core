import pytest
from pydantic import conlist

from orchestrator.db import ProductTable, db
from orchestrator.db.models import FixedInputTable
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_type_list_union(test_product_sub_block_one, test_product_sub_block_two):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one
    SubBlockTwoForTestInactive, SubBlockTwoForTestProvisioning, SubBlockTwoForTest = test_product_sub_block_two

    def list_of_ports(t):
        return conlist(t, min_length=1)

    class ProductListUnionInactive(SubscriptionModel, is_base=True):
        test_fixed_input: bool
        list_union_blocks: list_of_ports(SubBlockTwoForTestInactive | SubBlockOneForTestInactive)

    class ProductListUnionProvisioning(ProductListUnionInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_fixed_input: bool
        list_union_blocks: list_of_ports(SubBlockTwoForTestProvisioning | SubBlockOneForTestProvisioning)

    class ProductListUnion(ProductListUnionProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        list_union_blocks: list_of_ports(SubBlockTwoForTest | SubBlockOneForTest)

    SUBSCRIPTION_MODEL_REGISTRY["ProductListUnion"] = ProductListUnion
    yield ProductListUnionInactive, ProductListUnionProvisioning, ProductListUnion
    del SUBSCRIPTION_MODEL_REGISTRY["ProductListUnion"]


@pytest.fixture
def test_product_list_union(test_product_sub_block_one_db, test_product_sub_block_two_db):
    product = ProductTable(
        name="ProductListUnion",
        description="Test List Union Product",
        product_type="Test",
        tag="Union",
        status="active",
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    product.fixed_inputs = [fixed_input]
    product.product_blocks = [test_product_sub_block_one_db, test_product_sub_block_two_db]
    db.session.add(product)
    db.session.commit()
    return product.product_id

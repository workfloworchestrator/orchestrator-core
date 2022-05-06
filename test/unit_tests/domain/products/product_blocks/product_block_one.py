from typing import List, Optional

import pytest
from pydantic import Field

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel, ProductModel
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_block_one(test_product_sub_block_one):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestInactive(ProductBlockModel, product_block_name="ProductBlockOneForTest"):
        sub_block: SubBlockOneForTestInactive
        sub_block_2: Optional[SubBlockOneForTestInactive] = None
        sub_block_list: List[SubBlockOneForTestInactive] = []
        int_field: Optional[int] = None
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class ProductBlockOneForTestProvisioning(
        ProductBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        sub_block: SubBlockOneForTestProvisioning
        sub_block_2: SubBlockOneForTestProvisioning
        sub_block_list: List[SubBlockOneForTestProvisioning]
        int_field: int
        str_field: Optional[str] = None
        list_field: List[int]

    class ProductBlockOneForTest(ProductBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: List[SubBlockOneForTest]
        int_field: int
        str_field: str
        list_field: List[int]

    return ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest


@pytest.fixture
def test_product_block_one_db(resource_type_list, resource_type_int, resource_type_str, test_product_sub_block_one_db):
    product_block = ProductBlockTable(
        name="ProductBlockOneForTest", description="Test Block", tag="TEST", status="active"
    )

    product_block.resource_types = [resource_type_int, resource_type_str, resource_type_list]
    product_block.depends_on = [test_product_sub_block_one_db]

    db.session.add(product_block)
    db.session.commit()

    return product_block, test_product_sub_block_one_db


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

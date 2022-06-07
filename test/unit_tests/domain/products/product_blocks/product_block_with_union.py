from typing import List, Optional, Union

import pytest
from pydantic import Field

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_block_with_union(test_product_sub_block_one, test_product_sub_block_two):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one
    SubBlockTwoForTestInactive, SubBlockTwoForTestProvisioning, SubBlockTwoForTest = test_product_sub_block_two

    class ProductBlockWithUnionForTestInactive(ProductBlockModel, product_block_name="ProductBlockWithUnionForTest"):
        union_block: Optional[Union[SubBlockOneForTestInactive, SubBlockTwoForTestInactive]] = None
        int_field: Optional[int] = None
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class ProductBlockWithUnionForTestProvisioning(
        ProductBlockWithUnionForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        union_block: Union[SubBlockOneForTestProvisioning, SubBlockTwoForTestProvisioning]
        int_field: int
        str_field: Optional[str] = None
        list_field: List[int]

    class ProductBlockWithUnionForTest(
        ProductBlockWithUnionForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        union_block: Union[SubBlockOneForTest, SubBlockTwoForTest]
        int_field: int
        str_field: str
        list_field: List[int]

    return ProductBlockWithUnionForTestInactive, ProductBlockWithUnionForTestProvisioning, ProductBlockWithUnionForTest


@pytest.fixture
def test_product_block_with_union_db(
    test_product_block_one_db,
    test_product_sub_block_one_db,
    test_product_sub_block_two_db,
    resource_type_int,
    resource_type_str,
    resource_type_list,
):
    product_block, product_sub_block = test_product_block_one_db
    product_union_sub_block = ProductBlockTable(
        name="ProductBlockWithUnionForTest", description="Test Union Sub Block", tag="TEST", status="active"
    )
    product_union_sub_block.resource_types = [resource_type_int, resource_type_str, resource_type_list]
    product_union_sub_block.depends_on.append(test_product_sub_block_one_db)
    product_union_sub_block.depends_on.append(test_product_sub_block_two_db)
    db.session.add(product_union_sub_block)
    product_block.depends_on.append(product_union_sub_block)
    db.session.commit()

    return product_block, product_sub_block, product_union_sub_block

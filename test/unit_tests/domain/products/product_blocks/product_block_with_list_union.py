from typing import List, Optional, Union

import pytest
from pydantic import Field

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_block_with_list_union(test_product_sub_block_one, test_product_sub_block_two):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one
    SubBlockTwoForTestInactive, SubBlockTwoForTestProvisioning, SubBlockTwoForTest = test_product_sub_block_two

    class ProductBlockWithListUnionForTestInactive(
        ProductBlockModel, product_block_name="ProductBlockWithListUnionForTest"
    ):
        list_union_blocks: List[Union[SubBlockTwoForTestInactive, SubBlockOneForTestInactive]]
        int_field: Optional[int] = None
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class ProductBlockWithListUnionForTestProvisioning(
        ProductBlockWithListUnionForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        list_union_blocks: List[Union[SubBlockTwoForTestProvisioning, SubBlockOneForTestProvisioning]]
        int_field: int
        str_field: Optional[str] = None
        list_field: List[int]

    class ProductBlockWithListUnionForTest(
        ProductBlockWithListUnionForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        list_union_blocks: List[Union[SubBlockTwoForTest, SubBlockOneForTest]]
        int_field: int
        str_field: str
        list_field: List[int]

    return (
        ProductBlockWithListUnionForTestInactive,
        ProductBlockWithListUnionForTestProvisioning,
        ProductBlockWithListUnionForTest,
    )


@pytest.fixture
def test_product_block_with_list_union_db(
    test_product_sub_block_one_db,
    test_product_sub_block_two_db,
    resource_type_int,
    resource_type_str,
    resource_type_list,
):
    product_sub_block_one = test_product_sub_block_one_db
    product_sub_block_two = test_product_sub_block_two_db

    product_block_with_list_union = ProductBlockTable(
        name="ProductBlockWithListUnionForTest", description="Test Union Sub Block", tag="TEST", status="active"
    )
    product_block_with_list_union.resource_types = [resource_type_int, resource_type_str, resource_type_list]
    product_block_with_list_union.depends_on = [product_sub_block_one, product_sub_block_two]
    db.session.add(product_block_with_list_union)
    db.session.commit()

    return product_block_with_list_union, product_sub_block_one, product_sub_block_two

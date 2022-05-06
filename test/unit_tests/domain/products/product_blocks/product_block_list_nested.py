from typing import List, Optional

import pytest

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


class ProductBlockListNestedForTestInactive(ProductBlockModel, product_block_name="ProductBlockListNestedForTest"):
    sub_block_list: List["ProductBlockListNestedForTestInactive"]
    int_field: Optional[int] = None


class ProductBlockListNestedForTestProvisioning(
    ProductBlockListNestedForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    sub_block_list: List["ProductBlockListNestedForTestProvisioning"]  # type: ignore
    int_field: int


class ProductBlockListNestedForTest(
    ProductBlockListNestedForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
):
    sub_block_list: List["ProductBlockListNestedForTest"]  # type: ignore
    int_field: int


@pytest.fixture
def test_product_block_list_nested():
    # Classes defined at module level, otherwise they remain in local namespace and
    # `get_type_hints()` can't evaluate the ForwardRefs
    return (
        ProductBlockListNestedForTestInactive,
        ProductBlockListNestedForTestProvisioning,
        ProductBlockListNestedForTest,
    )


@pytest.fixture
def test_product_block_list_nested_db_in_use_by_block(resource_type_list, resource_type_int, resource_type_str):
    in_use_by_block = ProductBlockTable(
        name="ProductBlockListNestedForTest", description="Test Block Parent", tag="TEST", status="active"
    )
    in_use_by_block.resource_types = [resource_type_int]

    db.session.add(in_use_by_block)
    db.session.commit()

    return in_use_by_block

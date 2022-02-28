from typing import Optional

import pytest

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


class ProductBlockOneNestedForTestInactive(ProductBlockModel, product_block_name="ProductBlockOneNestedForTest"):
    sub_block: Optional["ProductBlockOneNestedForTestInactive"] = None
    int_field: Optional[int] = None


class ProductBlockOneNestedForTestProvisioning(
    ProductBlockOneNestedForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    sub_block: Optional["ProductBlockOneNestedForTestProvisioning"] = None
    int_field: int


class ProductBlockOneNestedForTest(ProductBlockOneNestedForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    sub_block: Optional["ProductBlockOneNestedForTest"] = None
    int_field: int


@pytest.fixture
def test_product_block_one_nested():
    # Classes defined at module level, otherwise they remain in local namespace and
    # `get_type_hints()` can't evaluate the ForwardRefs
    return ProductBlockOneNestedForTestInactive, ProductBlockOneNestedForTestProvisioning, ProductBlockOneNestedForTest


@pytest.fixture
def test_product_block_one_nested_db_parent(resource_type_list, resource_type_int, resource_type_str):
    parent_block = ProductBlockTable(
        name="ProductBlockOneNestedForTest", description="Test Block Parent", tag="TEST", status="active"
    )
    parent_block.resource_types = [resource_type_int]

    db.session.add(parent_block)
    db.session.commit()

    return parent_block

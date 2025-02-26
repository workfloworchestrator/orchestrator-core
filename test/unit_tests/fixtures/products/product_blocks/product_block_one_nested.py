from typing import Optional

import pytest

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.helpers import safe_delete_product_block_id


# Note: don't use these classes directly. Use the `test_product_block_one_nested` fixture to ensure proper teardown.
class ProductBlockOneNestedForTestInactive(ProductBlockModel, product_block_name="ProductBlockOneNestedForTest"):
    sub_block: Optional["ProductBlockOneNestedForTestInactive"] = None
    int_field: int | None = None


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
    blocks = (
        ProductBlockOneNestedForTestInactive,
        ProductBlockOneNestedForTestProvisioning,
        ProductBlockOneNestedForTest,
    )

    yield blocks

    for block in blocks:
        safe_delete_product_block_id(block)


@pytest.fixture
def test_product_block_one_nested_db_in_use_by_block(resource_type_list, resource_type_int, resource_type_str):
    in_use_by_block = ProductBlockTable(
        name="ProductBlockOneNestedForTest", description="Test Block Parent", tag="TEST", status="active"
    )
    in_use_by_block.resource_types = [resource_type_int]

    db.session.add(in_use_by_block)
    db.session.commit()

    return in_use_by_block

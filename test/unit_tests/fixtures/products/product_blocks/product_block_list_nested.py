from typing import Annotated

import pytest
import strawberry

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.helpers import safe_delete_product_block_id


class ProductBlockListNestedForTestInactive(ProductBlockModel, product_block_name="ProductBlockListNestedForTest"):
    sub_block_list: list["ProductBlockListNestedForTestInactive"]
    int_field: int | None = None


class ProductBlockListNestedForTestProvisioning(
    ProductBlockListNestedForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    sub_block_list: list["ProductBlockListNestedForTestProvisioning"]  # type: ignore
    int_field: int


class ProductBlockListNestedForTest(
    ProductBlockListNestedForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
):
    sub_block_list: list["ProductBlockListNestedForTest"]  # type: ignore
    int_field: int


ProductBlockListNestedForTestType = Annotated[
    "ProductBlockListNestedForTestInactiveGraphql", strawberry.lazy(".product_block_list_nested")
]


@strawberry.experimental.pydantic.type(model=ProductBlockListNestedForTestInactive)
class ProductBlockListNestedForTestInactiveGraphql:
    sub_block_list: list[ProductBlockListNestedForTestType]
    int_field: int


@pytest.fixture
def test_product_block_list_nested(test_product_block_list_nested_db_in_use_by_block):
    # Classes defined at module level, otherwise they remain in local namespace and
    # `get_type_hints()` can't evaluate the ForwardRefs
    yield (
        ProductBlockListNestedForTestInactive,
        ProductBlockListNestedForTestProvisioning,
        ProductBlockListNestedForTest,
    )

    safe_delete_product_block_id(ProductBlockListNestedForTestInactive)
    safe_delete_product_block_id(ProductBlockListNestedForTestProvisioning)
    safe_delete_product_block_id(ProductBlockListNestedForTest)


@pytest.fixture
def test_product_block_list_nested_db_in_use_by_block(resource_type_list, resource_type_int, resource_type_str):
    in_use_by_block = ProductBlockTable(
        name="ProductBlockListNestedForTest", description="Test Block Parent", tag="TEST", status="active"
    )
    in_use_by_block.resource_types = [resource_type_int]

    db.session.add(in_use_by_block)
    db.session.commit()

    return in_use_by_block

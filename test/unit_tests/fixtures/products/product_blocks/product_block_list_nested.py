# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from orchestrator.core.db import ProductBlockTable, db
from orchestrator.core.domain.base import ProductBlockModel
from orchestrator.core.types import SubscriptionLifecycle
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

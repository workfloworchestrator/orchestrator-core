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
from pydantic import Field

from orchestrator.core.db import ProductBlockTable, db
from orchestrator.core.domain.base import ProductBlockModel
from orchestrator.core.types import SubscriptionLifecycle


@pytest.fixture
def test_product_block_with_list_union(test_product_sub_block_one, test_product_sub_block_two):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one
    SubBlockTwoForTestInactive, SubBlockTwoForTestProvisioning, SubBlockTwoForTest = test_product_sub_block_two

    class ProductBlockWithListUnionForTestInactive(
        ProductBlockModel, product_block_name="ProductBlockWithListUnionForTest"
    ):
        list_union_blocks: list[SubBlockTwoForTestInactive | SubBlockOneForTestInactive]
        int_field: int | None = None
        str_field: str | None = None
        list_field: list[int] = Field(default_factory=list)

    class ProductBlockWithListUnionForTestProvisioning(
        ProductBlockWithListUnionForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        list_union_blocks: list[SubBlockTwoForTestProvisioning | SubBlockOneForTestProvisioning]
        int_field: int
        str_field: str | None = None
        list_field: list[int]

    class ProductBlockWithListUnionForTest(
        ProductBlockWithListUnionForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        list_union_blocks: list[SubBlockTwoForTest | SubBlockOneForTest]
        int_field: int
        str_field: str
        list_field: list[int]

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

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
from pydantic import conlist

from orchestrator.core.db import ProductTable, db
from orchestrator.core.db.models import FixedInputTable
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.types import SubscriptionLifecycle


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

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

from orchestrator.core.db import FixedInputTable, ProductTable, db
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import ProductModel, SubscriptionModel
from orchestrator.core.domain.lifecycle import ProductLifecycle
from orchestrator.core.types import SubscriptionLifecycle
from test.integration_tests.fixtures.products.product_blocks.product_block_one_nested import (
    ProductBlockOneNestedForTest,
    ProductBlockOneNestedForTestInactive,
    ProductBlockOneNestedForTestProvisioning,
)


@pytest.fixture
def test_product_type_one_nested():
    class ProductTypeOneNestedForTestInactive(SubscriptionModel, is_base=True):
        test_fixed_input: bool
        block: ProductBlockOneNestedForTestInactive

    class ProductTypeOneNestedForTestProvisioning(
        ProductTypeOneNestedForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        test_fixed_input: bool
        block: ProductBlockOneNestedForTestProvisioning

    class ProductTypeOneNestedForTest(
        ProductTypeOneNestedForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        test_fixed_input: bool
        block: ProductBlockOneNestedForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOneNested"] = ProductTypeOneNestedForTest
    yield ProductTypeOneNestedForTestInactive, ProductTypeOneNestedForTestProvisioning, ProductTypeOneNestedForTest
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductOneNested"]


@pytest.fixture
def test_product_one_nested(test_product_block_one_nested_db_in_use_by_block, generic_product_block_chain):
    product = ProductTable(
        name="TestProductOneNested", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    pb_1 = test_product_block_one_nested_db_in_use_by_block
    pb_2, pb_3 = generic_product_block_chain
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [pb_1, pb_2, pb_3]

    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def test_product_model_nested(test_product_one_nested):
    return ProductModel(
        product_id=test_product_one_nested,
        name="TestProductOneNested",
        description="Test ProductTable",
        product_type="Test",
        tag="TEST",
        status=ProductLifecycle.ACTIVE,
    )

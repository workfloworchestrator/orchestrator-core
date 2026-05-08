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

from uuid import uuid4

import pytest
from sqlalchemy import select

from orchestrator.core.db import FixedInputTable, ProductTable, db
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import ProductModel, SubscriptionModel
from orchestrator.core.domain.lifecycle import ProductLifecycle
from orchestrator.core.types import SubscriptionLifecycle
from test.integration_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


@pytest.fixture
def test_product_type_one(test_product_block_one):
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one

    class ProductTypeOneForTestInactive(SubscriptionModel, is_base=True):
        test_fixed_input: bool
        block: ProductBlockOneForTestInactive

    class ProductTypeOneForTestProvisioning(
        ProductTypeOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        test_fixed_input: bool
        block: ProductBlockOneForTestProvisioning

    class ProductTypeOneForTest(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTest
    yield ProductTypeOneForTestInactive, ProductTypeOneForTestProvisioning, ProductTypeOneForTest
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"]


@pytest.fixture
def test_product_one(test_product_block_one_db):
    product = ProductTable(
        name="TestProductOne", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    product_block, _ = test_product_block_one_db
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [product_block]

    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def test_product_model(test_product_one):
    product = db.session.scalars(select(ProductTable).where(ProductTable.product_id == test_product_one)).one()

    return ProductModel(
        product_id=test_product_one,
        name="TestProductOne",
        description="Test ProductTable",
        product_type="Test",
        tag="TEST",
        status=ProductLifecycle.ACTIVE,
        created_at=product.created_at,
    )


@pytest.fixture
def product_one_subscription_1(test_product_one, test_product_type_one, test_product_sub_block_one):
    ProductTypeOneForTestInactive, _, ProductTypeOneForTest = test_product_type_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    model = ProductTypeOneForTestInactive.from_product_id(
        product_id=test_product_one,
        customer_id=str(uuid4()),
        status=SubscriptionLifecycle.INITIAL,
        insync=True,
        description="product one sub description",
    )
    model.block.str_field = "A"
    model.block.int_field = 1
    model.block.list_field = [10, 20, 30]
    model.block.enum_field = DummyEnum.BAR
    model.block.sub_block.str_field = "B"
    model.block.sub_block.int_field = 2
    model.block.sub_block_2 = SubBlockOneForTest.new(
        subscription_id=model.subscription_id, int_field=3, str_field="test"
    )

    model = ProductTypeOneForTest.from_other_lifecycle(model, SubscriptionLifecycle.ACTIVE)
    model.save()
    db.session.commit()
    return model.subscription_id

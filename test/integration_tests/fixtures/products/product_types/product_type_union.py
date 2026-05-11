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

from orchestrator.core.db import ProductTable, db
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.types import SubscriptionLifecycle


@pytest.fixture
def test_union_type_product(test_product_block_one, test_product_sub_block_one):
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one

    class UnionProductInactive(SubscriptionModel, is_base=True):
        test_block: ProductBlockOneForTestInactive | None
        union_block: ProductBlockOneForTestInactive | SubBlockOneForTestInactive | None

    class UnionProductProvisioning(UnionProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockOneForTestProvisioning
        union_block: ProductBlockOneForTestProvisioning | SubBlockOneForTestProvisioning

    class UnionProduct(UnionProductProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockOneForTest
        union_block: ProductBlockOneForTest | SubBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["UnionProduct"] = UnionProduct
    yield UnionProductInactive, UnionProductProvisioning, UnionProduct
    del SUBSCRIPTION_MODEL_REGISTRY["UnionProduct"]


@pytest.fixture
def test_union_product(test_product_block_one_db):
    product = ProductTable(
        name="UnionProduct", description="Test Union Product", product_type="Test", tag="Union", status="active"
    )

    product_block, product_sub_block = test_product_block_one_db
    product.product_blocks = [product_block, product_sub_block]
    db.session.add(product)
    db.session.commit()
    return product.product_id

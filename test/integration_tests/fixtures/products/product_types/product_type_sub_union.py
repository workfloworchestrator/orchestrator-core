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
def test_union_type_sub_product(test_product_block_with_union):
    (
        ProductBlockWithUnionForTestInactive,
        ProductBlockWithUnionForTestProvisioning,
        ProductBlockWithUnionForTest,
    ) = test_product_block_with_union

    class UnionProductSubInactive(SubscriptionModel, is_base=True):
        test_block: ProductBlockWithUnionForTestInactive | None

    class UnionProductSubProvisioning(UnionProductSubInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockWithUnionForTestProvisioning

    class UnionProductSub(UnionProductSubProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockWithUnionForTest

    SUBSCRIPTION_MODEL_REGISTRY["UnionProductSub"] = UnionProductSub
    yield UnionProductSubInactive, UnionProductSubProvisioning, UnionProductSub
    del SUBSCRIPTION_MODEL_REGISTRY["UnionProductSub"]


@pytest.fixture
def test_union_sub_product(test_product_block_with_union_db):
    product = ProductTable(
        name="UnionProductSub",
        description="Product with Union sub product_block",
        tag="UnionSub",
        product_type="Test",
        status="active",
    )
    _, _, product_union_sub_block = test_product_block_with_union_db
    product.product_blocks = [product_union_sub_block]
    db.session.add(product)
    db.session.commit()

    return product.product_id

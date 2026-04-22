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


@pytest.fixture
def test_product_sub_block_two():
    class SubBlockTwoForTestInactive(ProductBlockModel, product_block_name="SubBlockTwoForTest"):
        int_field_2: int  # TODO #430 inactive productblocks should not have required fields

    class SubBlockTwoForTestProvisioning(SubBlockTwoForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        int_field_2: int

    class SubBlockTwoForTest(SubBlockTwoForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field_2: int

    return SubBlockTwoForTestInactive, SubBlockTwoForTestProvisioning, SubBlockTwoForTest


@pytest.fixture
def test_product_sub_block_two_db(resource_type_int_2):
    sub_block = ProductBlockTable(
        name="SubBlockTwoForTest", description="Test Sub Block Two", tag="TEST", status="active"
    )

    sub_block.resource_types = [resource_type_int_2]

    db.session.add(sub_block)
    db.session.commit()
    return sub_block

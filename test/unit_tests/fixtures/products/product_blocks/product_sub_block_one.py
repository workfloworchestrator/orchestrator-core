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
def test_product_sub_block_one():
    class SubBlockOneForTestInactive(ProductBlockModel, product_block_name="SubBlockOneForTest"):
        int_field: int | None = None
        str_field: str | None = None

    class SubBlockOneForTestProvisioning(SubBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        int_field: int
        str_field: str | None = None

    class SubBlockOneForTest(SubBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field: int
        str_field: str

    return SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest


@pytest.fixture
def test_product_sub_block_one_db(resource_type_int, resource_type_str):
    sub_block = ProductBlockTable(
        name="SubBlockOneForTest", description="Test Sub Block One", tag="TEST", status="active"
    )

    sub_block.resource_types = [resource_type_int, resource_type_str]

    db.session.add(sub_block)
    db.session.commit()
    return sub_block

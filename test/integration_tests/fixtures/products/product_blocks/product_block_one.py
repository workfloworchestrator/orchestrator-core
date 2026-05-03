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

from enum import StrEnum, auto

import pytest
from pydantic import Field, computed_field

from orchestrator.core.db import ProductBlockTable, db
from orchestrator.core.domain.base import ProductBlockModel, ProductModel
from orchestrator.core.domain.lifecycle import ProductLifecycle
from orchestrator.core.types import SubscriptionLifecycle


class DummyEnum(StrEnum):
    FOO = auto()
    BAR = auto()


@pytest.fixture
def test_product_block_one(test_product_sub_block_one):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestInactive(ProductBlockModel, product_block_name="ProductBlockOneForTest"):
        sub_block: SubBlockOneForTestInactive
        sub_block_2: SubBlockOneForTestInactive | None = None
        sub_block_list: list[SubBlockOneForTestInactive] = []
        int_field: int | None = None
        str_field: str | None = None
        list_field: list[int] = Field(default_factory=list)
        enum_field: DummyEnum | None = None

        @computed_field  # type: ignore[untyped-decorator]
        @property
        def title(self) -> str:
            return f"{self.tag} ProductBlockOneForTestInactive int_field={self.int_field}"

    class ProductBlockOneForTestProvisioning(
        ProductBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        sub_block: SubBlockOneForTestProvisioning
        sub_block_2: SubBlockOneForTestProvisioning
        sub_block_list: list[SubBlockOneForTestProvisioning]
        int_field: int
        str_field: str | None = None
        list_field: list[int]
        enum_field: DummyEnum

    class ProductBlockOneForTest(ProductBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        int_field: int
        str_field: str
        list_field: list[int]
        enum_field: DummyEnum

    return ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest


@pytest.fixture
def test_product_block_one_db(
    resource_type_list, resource_type_int, resource_type_str, resource_type_enum, test_product_sub_block_one_db
):
    product_block = ProductBlockTable(
        name="ProductBlockOneForTest", description="Test Block", tag="TEST", status="active"
    )

    product_block.resource_types = [resource_type_int, resource_type_str, resource_type_list, resource_type_enum]
    product_block.depends_on = [test_product_sub_block_one_db]

    db.session.add(product_block)
    db.session.commit()

    return product_block, test_product_sub_block_one_db


@pytest.fixture
def test_product_model(test_product_one):
    return ProductModel(
        product_id=test_product_one,
        name="TestProductOne",
        description="Test ProductTable",
        product_type="Test",
        tag="TEST",
        status=ProductLifecycle.ACTIVE,
    )

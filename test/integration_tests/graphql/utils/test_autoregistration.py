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

from orchestrator.core.graphql.autoregistration import create_strawberry_enums
from test.integration_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


def test_create_strawberry_enums(test_product_block_one):
    _, _, ProductBlockOneForTest = test_product_block_one
    assert create_strawberry_enums(ProductBlockOneForTest, {}) == {"enum_field": DummyEnum}


def test_create_strawberry_enums_optional(test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one
    assert create_strawberry_enums(ProductBlockOneForTestInactive, {}) == {"enum_field": DummyEnum}

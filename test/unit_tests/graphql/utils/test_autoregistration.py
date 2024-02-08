from orchestrator.graphql.autoregistration import create_strawberry_enums
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


def test_create_strawberry_enums(test_product_block_one):
    _, _, ProductBlockOneForTest = test_product_block_one
    assert create_strawberry_enums(ProductBlockOneForTest, {}) == {"enum_field": DummyEnum}


def test_create_strawberry_enums_optional(test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one
    assert create_strawberry_enums(ProductBlockOneForTestInactive, {}) == {"enum_field": DummyEnum}

from uuid import UUID

from orchestrator.search.core.types import ExtractedField, FieldType

from ..utils import fields


def get_simple_product_expected_fields(product_uuid: UUID) -> list[ExtractedField]:

    return fields(
        [
            ("product.description", "Product with basic block", FieldType.STRING),
            ("product.name", "Simple Product", FieldType.STRING),
            ("product.product_id", str(product_uuid), FieldType.UUID),
            ("product.product_type", "Simple", FieldType.STRING),
            ("product.status", "active", FieldType.STRING),
            ("product.tag", "SIMPLE", FieldType.STRING),
            ("product.simple_product.product_block.basic_block", "basic_block", FieldType.BLOCK),
            ("product.simple_product.product_block.basic_block.name", "name", FieldType.RESOURCE_TYPE),
            ("product.simple_product.product_block.basic_block.value", "value", FieldType.RESOURCE_TYPE),
            ("product.simple_product.product_block.basic_block.enabled", "enabled", FieldType.RESOURCE_TYPE),
        ]
    )


def get_nested_product_expected_fields(product_uuid: UUID) -> list[ExtractedField]:
    """Simplified expected fields for nested product - focus on nesting pattern."""

    return fields(
        [
            ("product.description", "Product with nested blocks", FieldType.STRING),
            ("product.name", "Nested Product", FieldType.STRING),
            ("product.product_id", str(product_uuid), FieldType.UUID),
            ("product.product_type", "Nested", FieldType.STRING),
            ("product.status", "active", FieldType.STRING),
            ("product.tag", "NESTED", FieldType.STRING),
            ("product.nested_product.product_block.outer_block", "outer_block", FieldType.BLOCK),
            ("product.nested_product.product_block.outer_block.middle_block", "middle_block", FieldType.BLOCK),
            (
                "product.nested_product.product_block.outer_block.middle_block.inner_block",
                "inner_block",
                FieldType.BLOCK,
            ),
            ("product.nested_product.product_block.outer_block.outer_name", "outer_name", FieldType.RESOURCE_TYPE),
            (
                "product.nested_product.product_block.outer_block.middle_block.middle_name",
                "middle_name",
                FieldType.RESOURCE_TYPE,
            ),
            (
                "product.nested_product.product_block.outer_block.middle_block.inner_block.inner_name",
                "inner_name",
                FieldType.RESOURCE_TYPE,
            ),
        ]
    )


def get_complex_product_expected_fields(product_uuid: UUID) -> list[ExtractedField]:
    """Simplified expected fields for complex product - focus on list/container patterns."""

    return fields(
        [
            ("product.description", "Product with complex container structures", FieldType.STRING),
            ("product.name", "Complex Product", FieldType.STRING),
            ("product.product_id", str(product_uuid), FieldType.UUID),
            ("product.product_type", "Complex", FieldType.STRING),
            ("product.status", "active", FieldType.STRING),
            ("product.tag", "COMPLEX", FieldType.STRING),
            ("product.complex_product.product_block.container_list", "container_list", FieldType.BLOCK),
            ("product.complex_product.product_block.container_list.endpoints", "endpoints", FieldType.RESOURCE_TYPE),
            ("product.complex_product.product_block.container_list.endpoints.0", "0", FieldType.BLOCK),
            (
                "product.complex_product.product_block.container_list.endpoints.0.block_list",
                "block_list",
                FieldType.RESOURCE_TYPE,
            ),
            ("product.complex_product.product_block.container_list.endpoints.0.block_list.0", "0", FieldType.BLOCK),
            (
                "product.complex_product.product_block.container_list.endpoints.0.singular_block",
                "singular_block",
                FieldType.BLOCK,
            ),
            (
                "product.complex_product.product_block.container_list.endpoints.0.union_block",
                "union_block",
                FieldType.BLOCK,
            ),
            (
                "product.complex_product.product_block.container_list.endpoints.0.string_field",
                "string_field",
                FieldType.RESOURCE_TYPE,
            ),
            (
                "product.complex_product.product_block.container_list.endpoints.0.int_field",
                "int_field",
                FieldType.RESOURCE_TYPE,
            ),
        ]
    )


def get_computed_product_expected_fields(product_uuid: UUID) -> list[ExtractedField]:
    """Simplified expected fields for computed product - verify computed property handling."""

    return fields(
        [
            ("product.description", "Product with computed property blocks", FieldType.STRING),
            ("product.name", "Computed Product", FieldType.STRING),
            ("product.product_id", str(product_uuid), FieldType.UUID),
            ("product.product_type", "Computed", FieldType.STRING),
            ("product.status", "active", FieldType.STRING),
            ("product.tag", "COMPUTED", FieldType.STRING),
            ("product.computed_product.product_block.device", "device", FieldType.BLOCK),
            ("product.computed_product.product_block.device.device_id", "device_id", FieldType.RESOURCE_TYPE),
            ("product.computed_product.product_block.device.device_name", "device_name", FieldType.RESOURCE_TYPE),
            (
                "product.computed_product.product_block.device.display_name",
                "display_name",
                FieldType.RESOURCE_TYPE,
            ),
            ("product.computed_product.product_block.device.status", "status", FieldType.RESOURCE_TYPE),
        ]
    )

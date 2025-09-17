from uuid import UUID
from orchestrator.search.core.types import ExtractedField, FieldType
from ..utils import fields


def get_simple_expected_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:
    """Expected fields for simple subscription traversal."""

    return fields(
        [
            ("subscription.subscription_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.customer_id", "test-customer", FieldType.STRING),
            ("subscription.description", "Initial subscription", FieldType.STRING),
            ("subscription.status", "initial", FieldType.STRING),
            ("subscription.insync", "False", FieldType.BOOLEAN),
            ("subscription.version", "1", FieldType.INTEGER),
            ("subscription.product.product_id", str(product_uuid), FieldType.UUID),
            ("subscription.product.name", "Simple Product", FieldType.STRING),
            ("subscription.product.description", "Product with basic block", FieldType.STRING),
            ("subscription.product.product_type", "Simple", FieldType.STRING),
            ("subscription.product.tag", "SIMPLE", FieldType.STRING),
            ("subscription.product.status", "active", FieldType.STRING),
            ("subscription.basic_block.subscription_instance_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.basic_block.owner_subscription_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.basic_block.name", "SimpleBlock", FieldType.STRING),
            ("subscription.basic_block.value", "42", FieldType.INTEGER),
            ("subscription.basic_block.enabled", "True", FieldType.BOOLEAN),
            ("subscription.basic_block.ratio", "1.5", FieldType.FLOAT),
            ("subscription.basic_block.created_at", "2024-01-15 10:30:00", FieldType.DATETIME),
        ]
    )


def get_nested_expected_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:
    """Expected fields for nested block traversal."""

    return fields(
        [
            ("subscription.subscription_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.customer_id", "test-customer", FieldType.STRING),
            ("subscription.description", "Initial subscription", FieldType.STRING),
            ("subscription.status", "initial", FieldType.STRING),
            ("subscription.insync", "False", FieldType.BOOLEAN),
            ("subscription.version", "1", FieldType.INTEGER),
            ("subscription.product.product_id", str(product_uuid), FieldType.UUID),
            ("subscription.product.name", "Nested Product", FieldType.STRING),
            ("subscription.product.description", "Product with nested blocks", FieldType.STRING),
            ("subscription.product.product_type", "Nested", FieldType.STRING),
            ("subscription.product.tag", "NESTED", FieldType.STRING),
            ("subscription.product.status", "active", FieldType.STRING),
            ("subscription.outer_block.subscription_instance_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.outer_block.owner_subscription_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.outer_block.middle_block.subscription_instance_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.outer_block.middle_block.owner_subscription_id", str(subscription_uuid), FieldType.UUID),
            (
                "subscription.outer_block.middle_block.inner_block.subscription_instance_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            (
                "subscription.outer_block.middle_block.inner_block.owner_subscription_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            ("subscription.outer_block.name", "OuterBlock", FieldType.STRING),
            ("subscription.outer_block.outer_name", "container", FieldType.STRING),
            ("subscription.outer_block.outer_total", "25", FieldType.INTEGER),
            ("subscription.outer_block.middle_block.name", "MiddleBlock", FieldType.STRING),
            ("subscription.outer_block.middle_block.middle_name", "nested", FieldType.STRING),
            ("subscription.outer_block.middle_block.middle_count", "5", FieldType.INTEGER),
            ("subscription.outer_block.middle_block.inner_block.name", "InnerBlock", FieldType.STRING),
            ("subscription.outer_block.middle_block.inner_block.inner_name", "deep", FieldType.STRING),
            ("subscription.outer_block.middle_block.inner_block.inner_value", "100", FieldType.INTEGER),
            ("subscription.outer_block.middle_block.inner_block.status", "active", FieldType.STRING),
        ]
    )


def get_complex_expected_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:
    """Expected fields from traversing the complex subscription instance."""

    return fields(
        [
            ("subscription.subscription_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.customer_id", "test-customer", FieldType.STRING),
            ("subscription.description", "Initial subscription", FieldType.STRING),
            ("subscription.status", "initial", FieldType.STRING),
            ("subscription.insync", "False", FieldType.BOOLEAN),
            ("subscription.version", "1", FieldType.INTEGER),
            ("subscription.product.product_id", str(product_uuid), FieldType.UUID),
            ("subscription.product.name", "Complex Product", FieldType.STRING),
            ("subscription.product.description", "Product with complex container structures", FieldType.STRING),
            ("subscription.product.product_type", "Complex", FieldType.STRING),
            ("subscription.product.tag", "COMPLEX", FieldType.STRING),
            ("subscription.product.status", "active", FieldType.STRING),
            ("subscription.container_list.subscription_instance_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.container_list.owner_subscription_id", str(subscription_uuid), FieldType.UUID),
            (
                "subscription.container_list.endpoints.0.subscription_instance_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            ("subscription.container_list.endpoints.0.owner_subscription_id", str(subscription_uuid), FieldType.UUID),
            (
                "subscription.container_list.endpoints.0.singular_block.subscription_instance_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            (
                "subscription.container_list.endpoints.0.singular_block.owner_subscription_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            (
                "subscription.container_list.endpoints.0.block_list.0.subscription_instance_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            (
                "subscription.container_list.endpoints.0.block_list.0.owner_subscription_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            (
                "subscription.container_list.endpoints.0.union_block.subscription_instance_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            (
                "subscription.container_list.endpoints.0.union_block.owner_subscription_id",
                str(subscription_uuid),
                FieldType.UUID,
            ),
            # Name fields
            ("subscription.container_list.name", "ContainerListBlock", FieldType.STRING),
            ("subscription.container_list.endpoints.0.name", "endpoint-1", FieldType.STRING),
            ("subscription.container_list.endpoints.0.singular_block.name", "singular", FieldType.STRING),
            ("subscription.container_list.endpoints.0.block_list.0.name", "prod", FieldType.STRING),
            ("subscription.container_list.endpoints.0.union_block.name", "AlternativeBlock", FieldType.STRING),
            # Basic fields
            ("subscription.container_list.endpoints.0.string_field", "test-string", FieldType.STRING),
            ("subscription.container_list.endpoints.0.int_field", "100", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.float_field", "3.14", FieldType.FLOAT),
            ("subscription.container_list.endpoints.0.last_seen", "2024-05-01 12:00:00", FieldType.DATETIME),
            # Integer lists
            (
                "subscription.container_list.endpoints.0.customer_ptp_ipv4_secondary_ipam_ids.0",
                "54783",
                FieldType.INTEGER,
            ),
            (
                "subscription.container_list.endpoints.0.customer_ptp_ipv4_secondary_ipam_ids.1",
                "54784",
                FieldType.INTEGER,
            ),
            ("subscription.container_list.endpoints.0.required_config_ids.0", "10", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.required_config_ids.1", "20", FieldType.INTEGER),
            # Float lists
            ("subscription.container_list.endpoints.0.modern_float_list.0", "1.1", FieldType.FLOAT),
            ("subscription.container_list.endpoints.0.modern_float_list.1", "2.2", FieldType.FLOAT),
            # Boolean lists
            ("subscription.container_list.endpoints.0.modern_bool_list.0", "True", FieldType.BOOLEAN),
            ("subscription.container_list.endpoints.0.modern_bool_list.1", "False", FieldType.BOOLEAN),
            # Enums
            ("subscription.container_list.endpoints.0.status", "active", FieldType.STRING),
            ("subscription.container_list.endpoints.0.priority", "3", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.status_list.0", "active", FieldType.STRING),
            ("subscription.container_list.endpoints.0.priority_list.0", "1", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.priority_list.1", "3", FieldType.INTEGER),
            # Nested lists
            ("subscription.container_list.endpoints.0.nested_int_lists.0.0", "1", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.nested_int_lists.0.1", "2", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.nested_int_lists.1.0", "3", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.nested_int_lists.1.1", "4", FieldType.INTEGER),
            # Union types
            ("subscription.container_list.endpoints.0.optional_primary_id", "12345", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.id_or_name", "999", FieldType.INTEGER),
            # Annotated and literal types
            ("subscription.container_list.endpoints.0.mtu_choice", "1500", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.customer_ipv4_mtu", "9000", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.mtu_values.0", "1500", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.mtu_values.1", "9000", FieldType.INTEGER),
            # Nested blocks
            ("subscription.container_list.endpoints.0.singular_block.value", "999", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.singular_block.enabled", "True", FieldType.BOOLEAN),
            ("subscription.container_list.endpoints.0.singular_block.ratio", "0.75", FieldType.FLOAT),
            (
                "subscription.container_list.endpoints.0.singular_block.created_at",
                "2024-05-01 12:00:00",
                FieldType.DATETIME,
            ),
            # Block lists
            ("subscription.container_list.endpoints.0.block_list.0.value", "1", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.block_list.0.enabled", "True", FieldType.BOOLEAN),
            ("subscription.container_list.endpoints.0.block_list.0.ratio", "1.0", FieldType.FLOAT),
            (
                "subscription.container_list.endpoints.0.block_list.0.created_at",
                "2024-05-01 12:00:00",
                FieldType.DATETIME,
            ),
            # Union blocks
            ("subscription.container_list.endpoints.0.union_block.optional_id", "777", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.union_block.id_or_name", "alternative-test", FieldType.STRING),
            ("subscription.container_list.endpoints.0.union_block.mtu_choice", "1500", FieldType.INTEGER),
            ("subscription.container_list.endpoints.0.union_block.validated_mtu", "9000", FieldType.INTEGER),
        ]
    )


def get_computed_property_expected_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:
    """Expected fields for computed property subscription traversal."""

    return fields(
        [
            ("subscription.subscription_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.customer_id", "test-customer", FieldType.STRING),
            ("subscription.description", "Initial subscription", FieldType.STRING),
            ("subscription.status", "initial", FieldType.STRING),
            ("subscription.insync", "False", FieldType.BOOLEAN),
            ("subscription.version", "1", FieldType.INTEGER),
            ("subscription.product.product_id", str(product_uuid), FieldType.UUID),
            ("subscription.product.name", "Computed Product", FieldType.STRING),
            ("subscription.product.description", "Product with computed property blocks", FieldType.STRING),
            ("subscription.product.product_type", "Computed", FieldType.STRING),
            ("subscription.product.tag", "COMPUTED", FieldType.STRING),
            ("subscription.product.status", "active", FieldType.STRING),
            ("subscription.device.subscription_instance_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.device.owner_subscription_id", str(subscription_uuid), FieldType.UUID),
            ("subscription.device.name", "TestDevice", FieldType.STRING),
            ("subscription.device.device_id", "123", FieldType.INTEGER),
            ("subscription.device.device_name", "Router", FieldType.STRING),
            ("subscription.device.status", "active", FieldType.STRING),
            ("subscription.device.display_name", "Router (123)", FieldType.STRING),
        ]
    )

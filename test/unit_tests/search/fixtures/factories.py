# Copyright 2019-2025 SURF, GÉANT.
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

from datetime import datetime
from typing import Any
from uuid import UUID

from orchestrator.domain.base import ProductModel
from orchestrator.domain.lifecycle import ProductLifecycle

from .blocks import (
    BasicBlock,
    ComputedBlock,
    ContainerBlock,
    ContainerListBlock,
    InnerBlock,
    MiddleBlock,
    OuterBlock,
    PriorityIntEnum,
    StatusEnum,
    UnionBlock,
)
from .subscriptions import (
    ComplexSubscription,
    ComputedPropertySubscription,
    NestedSubscription,
    SimpleSubscription,
)


def _create_test_product(name: str, description: str, product_type: str, tag: str, product_uuid: UUID) -> ProductModel:
    return ProductModel(
        product_id=product_uuid,
        name=name,
        description=description,
        product_type=product_type,
        tag=tag,
        status=ProductLifecycle.ACTIVE,
    )


def create_simple_subscription_instance(subscription_uuid: UUID, product_uuid: UUID) -> SimpleSubscription:
    basic_block = BasicBlock(
        name="SimpleBlock",
        subscription_instance_id=subscription_uuid,
        owner_subscription_id=subscription_uuid,
        value=42,
        enabled=True,
        ratio=1.5,
        created_at=datetime(2024, 1, 15, 10, 30, 0),
    )

    product = _create_test_product(
        name="Simple Product",
        description="Product with basic block",
        product_type="Simple",
        tag="SIMPLE",
        product_uuid=product_uuid,
    )

    return SimpleSubscription(
        subscription_id=subscription_uuid, product=product, customer_id="test-customer", basic_block=basic_block
    )


def create_nested_subscription_instance(subscription_uuid: UUID, product_uuid: UUID) -> NestedSubscription:
    """Create a nested subscription for testing deep block traversal."""

    inner_block = InnerBlock(
        name="InnerBlock",
        subscription_instance_id=subscription_uuid,
        owner_subscription_id=subscription_uuid,
        inner_name="deep",
        inner_value=100,
        status=StatusEnum.ACTIVE,
    )

    middle_block = MiddleBlock(
        name="MiddleBlock",
        subscription_instance_id=subscription_uuid,
        owner_subscription_id=subscription_uuid,
        middle_name="nested",
        inner_block=inner_block,
        middle_count=5,
    )

    outer_block = OuterBlock(
        name="OuterBlock",
        subscription_instance_id=subscription_uuid,
        owner_subscription_id=subscription_uuid,
        outer_name="container",
        middle_block=middle_block,
        outer_total=25,
    )

    product = _create_test_product(
        name="Nested Product",
        description="Product with nested blocks",
        product_type="Nested",
        tag="NESTED",
        product_uuid=product_uuid,
    )

    return NestedSubscription(
        subscription_id=subscription_uuid, product=product, customer_id="test-customer", outer_block=outer_block
    )


def create_complex_subscription_instance(subscription_uuid: UUID, product_uuid: UUID) -> ComplexSubscription:

    def create_basic_block(**kwargs: Any) -> BasicBlock:
        defaults = {
            "name": "ProductBlock",
            "subscription_instance_id": subscription_uuid,
            "owner_subscription_id": subscription_uuid,
            "value": 999,
            "enabled": True,
            "ratio": 0.75,
            "created_at": datetime(2024, 5, 1, 12, 0, 0),
        }
        merged_kwargs = {**defaults, **kwargs}
        return BasicBlock(**merged_kwargs)

    def create_union_block(**kwargs: Any) -> UnionBlock:
        defaults = {
            "name": "AlternativeBlock",
            "subscription_instance_id": subscription_uuid,
            "owner_subscription_id": subscription_uuid,
            "optional_id": 777,
            "id_or_name": "alternative-test",
            "mtu_choice": 1500,
            "validated_mtu": 9000,
        }
        merged_kwargs = {**defaults, **kwargs}
        return UnionBlock(**merged_kwargs)

    def create_container_block(**kwargs: Any) -> ContainerBlock:
        defaults = {
            "name": "EndpointBlock",
            "subscription_instance_id": subscription_uuid,
            "owner_subscription_id": subscription_uuid,
            "singular_block": create_basic_block(name="singular"),
            "customer_ptp_ipv4_secondary_ipam_ids": [54783, 54784],
            "string_field": "test-string",
            "int_field": 100,
            "block_list": [create_basic_block(name="prod", value=1, ratio=1.0)],
            "modern_float_list": [1.1, 2.2],
            "modern_bool_list": [True, False],
            "status": StatusEnum.ACTIVE,
            "priority": PriorityIntEnum.HIGH,
            "status_list": [StatusEnum.ACTIVE],
            "priority_list": [PriorityIntEnum.LOW, PriorityIntEnum.HIGH],
            "nested_int_lists": [[1, 2], [3, 4]],
            "optional_primary_id": 12345,
            "id_or_name": 999,
            "union_block": create_union_block(),
            "required_config_ids": [10, 20],
            "mtu_choice": 1500,
            "customer_ipv4_mtu": 9000,
            "mtu_values": [1500, 9000],
            "float_field": 3.14,
            "last_seen": datetime(2024, 5, 1, 12, 0, 0),
        }
        merged_kwargs = {**defaults, **kwargs}
        return ContainerBlock(**merged_kwargs)

    def create_container_list_block(**kwargs: Any) -> ContainerListBlock:
        defaults = {
            "name": "ContainerListBlock",
            "subscription_instance_id": subscription_uuid,
            "owner_subscription_id": subscription_uuid,
            "endpoints": [create_container_block(name="endpoint-1")],
        }
        merged_kwargs = {**defaults, **kwargs}
        return ContainerListBlock(**merged_kwargs)

    container_list = create_container_list_block()

    product = _create_test_product(
        name="Complex Product",
        description="Product with complex container structures",
        product_type="Complex",
        tag="COMPLEX",
        product_uuid=product_uuid,
    )

    return ComplexSubscription(
        subscription_id=subscription_uuid,
        product=product,
        customer_id="test-customer",
        container_list=container_list,
    )


def create_computed_property_subscription_instance(
    subscription_uuid: UUID, product_uuid: UUID
) -> ComputedPropertySubscription:

    device_block = ComputedBlock(
        name="TestDevice",
        subscription_instance_id=subscription_uuid,
        owner_subscription_id=subscription_uuid,
        device_id=123,
        device_name="Router",
        status="active",
    )

    product = _create_test_product(
        name="Computed Product",
        description="Product with computed property blocks",
        product_type="Computed",
        tag="COMPUTED",
        product_uuid=product_uuid,
    )

    return ComputedPropertySubscription(
        subscription_id=subscription_uuid, product=product, customer_id="test-customer", device=device_block
    )


# Product factory functions (products are just ProductModel instances, not subscription instances)


def create_simple_product_instance(product_uuid: UUID) -> ProductModel:
    """Create a simple product for testing basic product traversal."""
    return _create_test_product(
        name="Simple Product",
        description="Product with basic block",
        product_type="Simple",
        tag="SIMPLE",
        product_uuid=product_uuid,
    )


def create_nested_product_instance(product_uuid: UUID) -> ProductModel:
    """Create a nested product for testing nested product block schema traversal."""
    return _create_test_product(
        name="Nested Product",
        description="Product with nested blocks",
        product_type="Nested",
        tag="NESTED",
        product_uuid=product_uuid,
    )


def create_complex_product_instance(product_uuid: UUID) -> ProductModel:
    """Create a complex product for testing complex container structure schema traversal."""
    return _create_test_product(
        name="Complex Product",
        description="Product with complex container structures",
        product_type="Complex",
        tag="COMPLEX",
        product_uuid=product_uuid,
    )


def create_computed_product_instance(product_uuid: UUID) -> ProductModel:
    """Create a computed product for testing computed property block schema traversal."""
    return _create_test_product(
        name="Computed Product",
        description="Product with computed property blocks",
        product_type="Computed",
        tag="COMPUTED",
        product_uuid=product_uuid,
    )

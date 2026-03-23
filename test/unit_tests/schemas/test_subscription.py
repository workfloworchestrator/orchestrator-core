# Copyright 2019-2025 SURF.
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

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from orchestrator.schemas.subscription import (
    PortMode,
    SubscriptionBaseSchema,
    SubscriptionDomainModelSchema,
    SubscriptionIdSchema,
    SubscriptionInstanceBase,
    SubscriptionInstanceValueBaseSchema,
    SubscriptionRelationSchema,
    SubscriptionSchema,
    SubscriptionWithMetadata,
)
from orchestrator.types import SubscriptionLifecycle

# Shared test UUIDs
SUB_ID = uuid4()
PRODUCT_ID = uuid4()
PRODUCT_BLOCK_ID = uuid4()
RESOURCE_TYPE_ID = uuid4()
INSTANCE_ID = uuid4()
INSTANCE_VALUE_ID = uuid4()


def make_resource_type_schema() -> dict:
    return {
        "resource_type": "rt_name",
        "resource_type_id": str(uuid4()),
    }


def make_product_block_schema() -> dict:
    return {
        "product_block_id": str(uuid4()),
        "name": "block",
        "description": "A block",
        "status": "active",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def make_instance_value_schema() -> dict:
    return {
        "resource_type_id": str(RESOURCE_TYPE_ID),
        "subscription_instance_id": str(INSTANCE_ID),
        "subscription_instance_value_id": str(INSTANCE_VALUE_ID),
        "value": "some_value",
        "resource_type": make_resource_type_schema(),
    }


def make_relation_schema(parent_id: UUID | None = None, child_id: UUID | None = None) -> dict:
    return {
        "parent_id": str(parent_id or uuid4()),
        "child_id": str(child_id or uuid4()),
        "in_use_by_id": str(uuid4()),
        "depends_on_id": str(uuid4()),
        "order_id": 0,
    }


class TestPortMode:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("tagged", PortMode.TAGGED),
            ("untagged", PortMode.UNTAGGED),
            ("link_member", PortMode.LINKMEMBER),
        ],
        ids=["tagged", "untagged", "link_member"],
    )
    def test_port_mode_values_are_correct(self, value: str, expected: PortMode) -> None:
        assert PortMode(value) == expected

    def test_port_mode_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            PortMode("invalid")


class TestSubscriptionRelationSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        # Arrange / Act
        schema = SubscriptionRelationSchema(**make_relation_schema())

        # Assert
        assert isinstance(schema.parent_id, UUID)
        assert schema.order_id == 0

    def test_instantiate_with_domain_model_attr(self) -> None:
        data = {**make_relation_schema(), "domain_model_attr": "some_attr"}
        schema = SubscriptionRelationSchema(**data)
        assert schema.domain_model_attr == "some_attr"

    def test_instantiate_missing_required_field_raises(self) -> None:
        data = make_relation_schema()
        del data["parent_id"]
        with pytest.raises(ValidationError):
            SubscriptionRelationSchema(**data)

    def test_domain_model_attr_defaults_to_none(self) -> None:
        schema = SubscriptionRelationSchema(**make_relation_schema())
        assert schema.domain_model_attr is None


class TestSubscriptionInstanceValueBaseSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = SubscriptionInstanceValueBaseSchema(**make_instance_value_schema())
        assert isinstance(schema.resource_type_id, UUID)
        assert schema.value == "some_value"

    def test_instantiate_missing_required_raises(self) -> None:
        data = make_instance_value_schema()
        del data["value"]
        with pytest.raises(ValidationError):
            SubscriptionInstanceValueBaseSchema(**data)


class TestSubscriptionInstanceBase:
    def test_instantiate_valid_data_succeeds(self) -> None:
        data = {
            "subscription_id": str(SUB_ID),
            "product_block_id": str(PRODUCT_BLOCK_ID),
            "subscription_instance_id": str(INSTANCE_ID),
            "values": [make_instance_value_schema()],
            "parent_relations": [],
            "children_relations": [],
            "in_use_by_block_relations": [],
            "depends_on_block_relations": [],
            "product_block": make_product_block_schema(),
        }
        schema = SubscriptionInstanceBase(**data)
        assert isinstance(schema.subscription_id, UUID)
        assert schema.label is None

    def test_instantiate_with_label(self) -> None:
        data = {
            "subscription_id": str(SUB_ID),
            "product_block_id": str(PRODUCT_BLOCK_ID),
            "subscription_instance_id": str(INSTANCE_ID),
            "label": "my-label",
            "values": [],
            "parent_relations": [],
            "children_relations": [],
            "in_use_by_block_relations": [],
            "depends_on_block_relations": [],
            "product_block": make_product_block_schema(),
        }
        schema = SubscriptionInstanceBase(**data)
        assert schema.label == "my-label"


class TestSubscriptionBaseSchema:
    @pytest.mark.parametrize(
        "status",
        [
            SubscriptionLifecycle.INITIAL,
            SubscriptionLifecycle.ACTIVE,
            SubscriptionLifecycle.TERMINATED,
            SubscriptionLifecycle.PROVISIONING,
        ],
        ids=["initial", "active", "terminated", "provisioning"],
    )
    def test_instantiate_valid_status_succeeds(self, status: SubscriptionLifecycle) -> None:
        schema = SubscriptionBaseSchema(
            description="test sub",
            status=status,
            customer_id="customer-123",
            insync=True,
        )
        assert schema.status == status

    def test_optional_fields_default_to_none(self) -> None:
        schema = SubscriptionBaseSchema(
            description="test",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust",
            insync=False,
        )
        assert schema.subscription_id is None
        assert schema.start_date is None
        assert schema.product_id is None
        assert schema.note is None

    def test_instantiate_missing_required_description_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionBaseSchema(  # type: ignore[call-arg]
                status=SubscriptionLifecycle.ACTIVE,
                customer_id="cust",
                insync=True,
            )

    def test_instantiate_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionBaseSchema(
                description="x",
                status="not_a_status",  # type: ignore[arg-type]
                customer_id="c",
                insync=True,
            )


class TestSubscriptionSchema:
    def _make_product_base(self) -> dict:
        return {
            "name": "prod",
            "description": "a product",
            "product_type": "SomeType",
            "status": "active",
            "tag": "TAG",
        }

    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = SubscriptionSchema(
            subscription_id=str(SUB_ID),
            description="my sub",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust-1",
            insync=True,
            version=1,
        )
        assert schema.subscription_id == SUB_ID
        assert schema.version == 1

    def test_optional_fields_are_none_by_default(self) -> None:
        schema = SubscriptionSchema(
            subscription_id=str(SUB_ID),
            description="sub",
            status=SubscriptionLifecycle.INITIAL,
            customer_id="cust",
            insync=False,
            version=0,
        )
        assert schema.name is None
        assert schema.end_date is None
        assert schema.product is None
        assert schema.customer_descriptions is None
        assert schema.tag is None

    def test_instantiate_with_product(self) -> None:
        schema = SubscriptionSchema(
            subscription_id=str(SUB_ID),
            description="sub",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust",
            insync=True,
            version=2,
            product=self._make_product_base(),
        )
        assert schema.product is not None
        assert schema.product.name == "prod"

    def test_instantiate_missing_subscription_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionSchema(  # type: ignore[call-arg]
                description="sub",
                status=SubscriptionLifecycle.ACTIVE,
                customer_id="cust",
                insync=True,
                version=1,
            )


class TestSubscriptionWithMetadata:
    def test_instantiate_with_metadata_alias(self) -> None:
        schema = SubscriptionWithMetadata(
            subscription_id=str(SUB_ID),
            description="sub",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust",
            insync=True,
            version=1,
            metadata={"key": "value"},
        )
        assert schema.metadata_ == {"key": "value"}

    def test_instantiate_with_metadata_none(self) -> None:
        schema = SubscriptionWithMetadata(
            subscription_id=str(SUB_ID),
            description="sub",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust",
            insync=True,
            version=1,
            metadata=None,
        )
        assert schema.metadata_ is None


class TestSubscriptionIdSchema:
    def test_instantiate_valid_uuid_succeeds(self) -> None:
        schema = SubscriptionIdSchema(subscription_id=str(SUB_ID))
        assert schema.subscription_id == SUB_ID

    def test_instantiate_missing_uuid_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionIdSchema()  # type: ignore[call-arg]

    def test_instantiate_invalid_uuid_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionIdSchema(subscription_id="not-a-uuid")


class TestSubscriptionDomainModelSchema:
    def test_instantiate_with_product_required(self) -> None:
        product = {
            "name": "prod",
            "description": "desc",
            "product_type": "Type",
            "status": "active",
            "tag": "T",
        }
        schema = SubscriptionDomainModelSchema(
            subscription_id=str(SUB_ID),
            description="sub",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust",
            insync=True,
            version=1,
            product=product,
        )
        assert schema.product.name == "prod"
        assert schema.customer_descriptions == []

    def test_allows_extra_fields(self) -> None:
        product = {
            "name": "prod",
            "description": "desc",
            "product_type": "Type",
            "status": "active",
            "tag": "T",
        }
        schema = SubscriptionDomainModelSchema(
            subscription_id=str(SUB_ID),
            description="sub",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust",
            insync=True,
            version=1,
            product=product,
            extra_field="some_value",
        )
        assert schema.model_extra is not None
        assert schema.model_extra.get("extra_field") == "some_value"

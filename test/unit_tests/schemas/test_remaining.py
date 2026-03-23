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

"""Tests for smaller schemas.

Covers fixed_input, resource_type, product_block, problem_detail,
subscription_descriptions, and search schemas.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from orchestrator.db.models import DESCRIPTION_LENGTH
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas.fixed_input import FixedInputBaseSchema, FixedInputConfigurationItemSchema, FixedInputSchema
from orchestrator.schemas.problem_detail import ProblemDetailSchema
from orchestrator.schemas.product_block import ProductBlockBaseSchema, ProductBlockPatchSchema, ProductBlockSchema
from orchestrator.schemas.resource_type import ResourceTypeBaseSchema, ResourceTypePatchSchema, ResourceTypeSchema
from orchestrator.schemas.subscription_descriptions import (
    SubscriptionDescriptionBaseSchema,
    SubscriptionDescriptionSchema,
    UpdateSubscriptionDescriptionSchema,
)

FIXED_INPUT_ID = uuid4()
PRODUCT_ID = uuid4()
PRODUCT_BLOCK_ID = uuid4()
RESOURCE_TYPE_ID = uuid4()
SUBSCRIPTION_ID = uuid4()
DESCRIPTION_ID = uuid4()
NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# FixedInput schemas
# ---------------------------------------------------------------------------


class TestFixedInputBaseSchema:
    def test_instantiate_minimal_valid_data_succeeds(self) -> None:
        schema = FixedInputBaseSchema(name="bandwidth", value="1000")
        assert schema.name == "bandwidth"
        assert schema.value == "1000"

    def test_optional_fields_default_to_none(self) -> None:
        schema = FixedInputBaseSchema(name="speed", value="100")
        assert schema.fixed_input_id is None
        assert schema.product_id is None

    def test_instantiate_with_uuids(self) -> None:
        schema = FixedInputBaseSchema(
            fixed_input_id=FIXED_INPUT_ID,
            name="speed",
            value="100",
            product_id=PRODUCT_ID,
        )
        assert schema.fixed_input_id == FIXED_INPUT_ID
        assert schema.product_id == PRODUCT_ID

    def test_instantiate_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            FixedInputBaseSchema(value="100")  # type: ignore[call-arg]

    def test_instantiate_missing_value_raises(self) -> None:
        with pytest.raises(ValidationError):
            FixedInputBaseSchema(name="speed")  # type: ignore[call-arg]


class TestFixedInputSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = FixedInputSchema(
            fixed_input_id=FIXED_INPUT_ID,
            name="speed",
            value="1000",
            created_at=NOW,
            product_id=PRODUCT_ID,
        )
        assert schema.fixed_input_id == FIXED_INPUT_ID
        assert isinstance(schema.created_at, datetime)

    def test_instantiate_missing_fixed_input_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            FixedInputSchema(  # type: ignore[call-arg]
                name="speed",
                value="100",
                created_at=NOW,
                product_id=PRODUCT_ID,
            )

    def test_instantiate_missing_product_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            FixedInputSchema(  # type: ignore[call-arg]
                fixed_input_id=FIXED_INPUT_ID,
                name="speed",
                value="100",
                created_at=NOW,
            )

    def test_fixed_input_id_is_uuid_type(self) -> None:
        schema = FixedInputSchema(
            fixed_input_id=FIXED_INPUT_ID,
            name="x",
            value="y",
            created_at=NOW,
            product_id=PRODUCT_ID,
        )
        assert isinstance(schema.fixed_input_id, UUID)


class TestFixedInputConfigurationItemSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = FixedInputConfigurationItemSchema(
            name="speed",
            description="Speed option",
            values=["100", "1000", "10000"],
        )
        assert schema.name == "speed"
        assert schema.values == ["100", "1000", "10000"]

    def test_instantiate_with_empty_values_succeeds(self) -> None:
        schema = FixedInputConfigurationItemSchema(name="mode", description="Mode", values=[])
        assert schema.values == []

    def test_instantiate_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            FixedInputConfigurationItemSchema(description="d", values=[])  # type: ignore[call-arg]

    def test_instantiate_missing_description_raises(self) -> None:
        with pytest.raises(ValidationError):
            FixedInputConfigurationItemSchema(name="n", values=[])  # type: ignore[call-arg]

    def test_instantiate_missing_values_raises(self) -> None:
        with pytest.raises(ValidationError):
            FixedInputConfigurationItemSchema(name="n", description="d")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ResourceType schemas
# ---------------------------------------------------------------------------


class TestResourceTypeBaseSchema:
    def test_instantiate_minimal_valid_data_succeeds(self) -> None:
        schema = ResourceTypeBaseSchema(resource_type="ip_address")
        assert schema.resource_type == "ip_address"

    def test_optional_fields_default_to_none(self) -> None:
        schema = ResourceTypeBaseSchema(resource_type="vlan_id")
        assert schema.description is None
        assert schema.resource_type_id is None

    def test_instantiate_with_all_fields(self) -> None:
        schema = ResourceTypeBaseSchema(
            resource_type="vlan_id",
            description="A VLAN identifier",
            resource_type_id=RESOURCE_TYPE_ID,
        )
        assert schema.resource_type_id == RESOURCE_TYPE_ID
        assert schema.description == "A VLAN identifier"

    def test_instantiate_missing_resource_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            ResourceTypeBaseSchema()  # type: ignore[call-arg]


class TestResourceTypeSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = ResourceTypeSchema(
            resource_type="ip_prefix",
            resource_type_id=RESOURCE_TYPE_ID,
        )
        assert schema.resource_type_id == RESOURCE_TYPE_ID

    def test_instantiate_missing_resource_type_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            ResourceTypeSchema(resource_type="ip_prefix")  # type: ignore[call-arg]

    def test_resource_type_id_is_uuid_type(self) -> None:
        schema = ResourceTypeSchema(
            resource_type="x",
            resource_type_id=RESOURCE_TYPE_ID,
        )
        assert isinstance(schema.resource_type_id, UUID)


class TestResourceTypePatchSchema:
    def test_instantiate_with_description_succeeds(self) -> None:
        schema = ResourceTypePatchSchema(description="Updated description")
        assert schema.description == "Updated description"

    def test_instantiate_without_description_defaults_to_none(self) -> None:
        schema = ResourceTypePatchSchema()
        assert schema.description is None

    def test_description_at_max_length_succeeds(self) -> None:
        schema = ResourceTypePatchSchema(description="x" * DESCRIPTION_LENGTH)
        assert len(schema.description) == DESCRIPTION_LENGTH  # type: ignore[arg-type]

    def test_description_exceeding_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            ResourceTypePatchSchema(description="x" * (DESCRIPTION_LENGTH + 1))


# ---------------------------------------------------------------------------
# ProductBlock schemas
# ---------------------------------------------------------------------------


class TestProductBlockBaseSchema:
    def test_instantiate_minimal_valid_data_succeeds(self) -> None:
        schema = ProductBlockBaseSchema(name="IpBlock", description="An IP block")
        assert schema.name == "IpBlock"
        assert schema.description == "An IP block"

    def test_optional_fields_default_to_none(self) -> None:
        schema = ProductBlockBaseSchema(name="Block", description="desc")
        assert schema.product_block_id is None
        assert schema.tag is None
        assert schema.status is None
        assert schema.resource_types is None

    def test_instantiate_with_lifecycle_status(self) -> None:
        schema = ProductBlockBaseSchema(
            name="Block",
            description="desc",
            status=ProductLifecycle.ACTIVE,
        )
        assert schema.status == ProductLifecycle.ACTIVE

    def test_instantiate_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProductBlockBaseSchema(description="desc")  # type: ignore[call-arg]


class TestProductBlockSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = ProductBlockSchema(
            product_block_id=PRODUCT_BLOCK_ID,
            name="VlanBlock",
            description="A VLAN block",
            status=ProductLifecycle.ACTIVE,
            created_at=NOW,
        )
        assert schema.product_block_id == PRODUCT_BLOCK_ID
        assert schema.status == ProductLifecycle.ACTIVE

    def test_end_date_defaults_to_none(self) -> None:
        schema = ProductBlockSchema(
            product_block_id=PRODUCT_BLOCK_ID,
            name="Block",
            description="desc",
            status=ProductLifecycle.ACTIVE,
            created_at=NOW,
        )
        assert schema.end_date is None

    def test_resource_types_defaults_to_none(self) -> None:
        schema = ProductBlockSchema(
            product_block_id=PRODUCT_BLOCK_ID,
            name="Block",
            description="desc",
            status=ProductLifecycle.ACTIVE,
            created_at=NOW,
        )
        assert schema.resource_types is None

    def test_instantiate_missing_product_block_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProductBlockSchema(  # type: ignore[call-arg]
                name="Block",
                description="desc",
                status=ProductLifecycle.ACTIVE,
                created_at=NOW,
            )

    @pytest.mark.parametrize(
        "status",
        [ProductLifecycle.ACTIVE, ProductLifecycle.PRE_PRODUCTION, ProductLifecycle.PHASE_OUT],
        ids=["active", "pre_production", "phase_out"],
    )
    def test_instantiate_all_lifecycle_statuses_succeeds(self, status: ProductLifecycle) -> None:
        schema = ProductBlockSchema(
            product_block_id=PRODUCT_BLOCK_ID,
            name="Block",
            description="desc",
            status=status,
            created_at=NOW,
        )
        assert schema.status == status


class TestProductBlockPatchSchema:
    def test_instantiate_with_description_succeeds(self) -> None:
        schema = ProductBlockPatchSchema(description="New description")
        assert schema.description == "New description"

    def test_instantiate_without_description_defaults_to_none(self) -> None:
        schema = ProductBlockPatchSchema()
        assert schema.description is None

    def test_description_exceeding_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProductBlockPatchSchema(description="x" * (DESCRIPTION_LENGTH + 1))


# ---------------------------------------------------------------------------
# ProblemDetail schema
# ---------------------------------------------------------------------------


class TestProblemDetailSchema:
    def test_instantiate_empty_schema_all_none(self) -> None:
        schema = ProblemDetailSchema()
        assert schema.detail is None
        assert schema.status is None
        assert schema.title is None
        assert schema.type is None

    def test_instantiate_with_all_fields(self) -> None:
        schema = ProblemDetailSchema(
            detail="Resource not found",
            status=404,
            title="Not Found",
            type="https://example.com/errors/not-found",
        )
        assert schema.detail == "Resource not found"
        assert schema.status == 404
        assert schema.title == "Not Found"
        assert schema.type == "https://example.com/errors/not-found"

    @pytest.mark.parametrize(
        "status_code",
        [400, 401, 403, 404, 422, 500],
        ids=["bad_request", "unauthorized", "forbidden", "not_found", "unprocessable", "server_error"],
    )
    def test_instantiate_http_status_codes_succeed(self, status_code: int) -> None:
        schema = ProblemDetailSchema(status=status_code)
        assert schema.status == status_code

    def test_instantiate_with_partial_fields(self) -> None:
        schema = ProblemDetailSchema(status=500, title="Internal Server Error")
        assert schema.status == 500
        assert schema.title == "Internal Server Error"
        assert schema.detail is None
        assert schema.type is None


# ---------------------------------------------------------------------------
# SubscriptionDescription schemas
# ---------------------------------------------------------------------------


class TestSubscriptionDescriptionBaseSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = SubscriptionDescriptionBaseSchema(
            description="Custom description",
            customer_id="customer-abc",
            subscription_id=SUBSCRIPTION_ID,
        )
        assert schema.description == "Custom description"
        assert schema.customer_id == "customer-abc"
        assert schema.subscription_id == SUBSCRIPTION_ID

    def test_instantiate_missing_description_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionDescriptionBaseSchema(  # type: ignore[call-arg]
                customer_id="cust",
                subscription_id=SUBSCRIPTION_ID,
            )

    def test_instantiate_missing_customer_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionDescriptionBaseSchema(  # type: ignore[call-arg]
                description="desc",
                subscription_id=SUBSCRIPTION_ID,
            )

    def test_instantiate_missing_subscription_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionDescriptionBaseSchema(  # type: ignore[call-arg]
                description="desc",
                customer_id="cust",
            )

    def test_subscription_id_is_uuid_type(self) -> None:
        schema = SubscriptionDescriptionBaseSchema(
            description="desc",
            customer_id="cust",
            subscription_id=SUBSCRIPTION_ID,
        )
        assert isinstance(schema.subscription_id, UUID)


class TestSubscriptionDescriptionSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = SubscriptionDescriptionSchema(
            description="My description",
            customer_id="cust-1",
            subscription_id=SUBSCRIPTION_ID,
            id=DESCRIPTION_ID,
            version=1,
        )
        assert schema.id == DESCRIPTION_ID
        assert schema.version == 1

    def test_created_at_defaults_to_none(self) -> None:
        schema = SubscriptionDescriptionSchema(
            description="desc",
            customer_id="cust",
            subscription_id=SUBSCRIPTION_ID,
            id=DESCRIPTION_ID,
            version=0,
        )
        assert schema.created_at is None

    def test_instantiate_with_created_at(self) -> None:
        schema = SubscriptionDescriptionSchema(
            description="desc",
            customer_id="cust",
            subscription_id=SUBSCRIPTION_ID,
            id=DESCRIPTION_ID,
            created_at=NOW,
            version=2,
        )
        assert isinstance(schema.created_at, datetime)

    def test_instantiate_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionDescriptionSchema(  # type: ignore[call-arg]
                description="desc",
                customer_id="cust",
                subscription_id=SUBSCRIPTION_ID,
                version=1,
            )

    def test_instantiate_missing_version_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionDescriptionSchema(  # type: ignore[call-arg]
                description="desc",
                customer_id="cust",
                subscription_id=SUBSCRIPTION_ID,
                id=DESCRIPTION_ID,
            )


class TestUpdateSubscriptionDescriptionSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = UpdateSubscriptionDescriptionSchema(
            description="Updated",
            customer_id="cust",
            subscription_id=SUBSCRIPTION_ID,
            id=DESCRIPTION_ID,
        )
        assert schema.version is None

    def test_version_is_optional(self) -> None:
        schema = UpdateSubscriptionDescriptionSchema(
            description="desc",
            customer_id="cust",
            subscription_id=SUBSCRIPTION_ID,
            id=DESCRIPTION_ID,
            version=5,
        )
        assert schema.version == 5

    def test_created_at_is_optional(self) -> None:
        schema = UpdateSubscriptionDescriptionSchema(
            description="desc",
            customer_id="cust",
            subscription_id=SUBSCRIPTION_ID,
            id=DESCRIPTION_ID,
            created_at=NOW,
        )
        assert isinstance(schema.created_at, datetime)

    def test_instantiate_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            UpdateSubscriptionDescriptionSchema(  # type: ignore[call-arg]
                description="desc",
                customer_id="cust",
                subscription_id=SUBSCRIPTION_ID,
            )

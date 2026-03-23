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

from orchestrator.db.models import DESCRIPTION_LENGTH
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas.product import ProductBaseSchema, ProductPatchSchema, ProductSchema

PRODUCT_ID = uuid4()
NOW = datetime.now(tz=timezone.utc)


def make_product_base_data(**overrides) -> dict:
    return {
        "name": "Test Product",
        "description": "A test product",
        "product_type": "SomeProductType",
        "status": ProductLifecycle.ACTIVE,
        "tag": "TEST",
        **overrides,
    }


def make_product_schema_data(**overrides) -> dict:
    return {
        **make_product_base_data(),
        "product_id": str(PRODUCT_ID),
        "created_at": NOW.isoformat(),
        "product_blocks": [],
        "fixed_inputs": [],
        "workflows": [],
        **overrides,
    }


class TestProductBaseSchema:
    @pytest.mark.parametrize(
        "status",
        [
            ProductLifecycle.ACTIVE,
            ProductLifecycle.PRE_PRODUCTION,
            ProductLifecycle.PHASE_OUT,
            ProductLifecycle.END_OF_LIFE,
        ],
        ids=["active", "pre_production", "phase_out", "end_of_life"],
    )
    def test_instantiate_valid_status_succeeds(self, status: ProductLifecycle) -> None:
        schema = ProductBaseSchema(**make_product_base_data(status=status))
        assert schema.status == status

    def test_optional_fields_default_to_none(self) -> None:
        schema = ProductBaseSchema(**make_product_base_data())
        assert schema.product_id is None
        assert schema.created_at is None
        assert schema.end_date is None

    def test_instantiate_with_uuid_fields(self) -> None:
        schema = ProductBaseSchema(
            **make_product_base_data(
                product_id=str(PRODUCT_ID),
                created_at=NOW.isoformat(),
                end_date=NOW.isoformat(),
            )
        )
        assert schema.product_id == PRODUCT_ID
        assert isinstance(schema.created_at, datetime)
        assert isinstance(schema.end_date, datetime)

    def test_instantiate_missing_required_name_raises(self) -> None:
        data = make_product_base_data()
        del data["name"]
        with pytest.raises(ValidationError):
            ProductBaseSchema(**data)

    def test_instantiate_missing_required_tag_raises(self) -> None:
        data = make_product_base_data()
        del data["tag"]
        with pytest.raises(ValidationError):
            ProductBaseSchema(**data)

    def test_instantiate_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProductBaseSchema(**make_product_base_data(status="not_a_lifecycle"))

    def test_instantiate_missing_product_type_raises(self) -> None:
        data = make_product_base_data()
        del data["product_type"]
        with pytest.raises(ValidationError):
            ProductBaseSchema(**data)


class TestProductSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = ProductSchema(**make_product_schema_data())
        assert schema.product_id == PRODUCT_ID
        assert schema.product_blocks == []
        assert schema.fixed_inputs == []
        assert schema.workflows == []

    def test_instantiate_missing_product_id_raises(self) -> None:
        data = make_product_schema_data()
        del data["product_id"]
        with pytest.raises(ValidationError):
            ProductSchema(**data)

    def test_instantiate_missing_created_at_raises(self) -> None:
        data = make_product_schema_data()
        del data["created_at"]
        with pytest.raises(ValidationError):
            ProductSchema(**data)

    def test_product_id_is_uuid_type(self) -> None:
        schema = ProductSchema(**make_product_schema_data())
        assert isinstance(schema.product_id, UUID)

    def test_created_at_is_datetime_type(self) -> None:
        schema = ProductSchema(**make_product_schema_data())
        assert isinstance(schema.created_at, datetime)


class TestProductPatchSchema:
    def test_instantiate_with_description_succeeds(self) -> None:
        schema = ProductPatchSchema(description="New description")
        assert schema.description == "New description"

    def test_instantiate_without_description_defaults_to_none(self) -> None:
        schema = ProductPatchSchema()
        assert schema.description is None

    def test_description_at_max_length_succeeds(self) -> None:
        description = "x" * DESCRIPTION_LENGTH
        schema = ProductPatchSchema(description=description)
        assert len(schema.description) == DESCRIPTION_LENGTH  # type: ignore[arg-type]

    def test_description_exceeding_max_length_raises(self) -> None:
        description = "x" * (DESCRIPTION_LENGTH + 1)
        with pytest.raises(ValidationError):
            ProductPatchSchema(description=description)

    def test_description_empty_string_succeeds(self) -> None:
        schema = ProductPatchSchema(description="")
        assert schema.description == ""

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

"""Tests for API model helpers: validate (required column checks), transform_json (nested dict→ORM), cleanse_json (key stripping), parse_date_fields (timestamp/ISO parsing)."""

from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.core.api.error_handling import ProblemDetailException
from orchestrator.core.api.models import cleanse_json, delete, parse_date_fields, transform_json, validate
from orchestrator.core.db import ProductTable, ResourceTypeTable

# --- validate ---


def test_validate_missing_columns_raises() -> None:
    with pytest.raises(ProblemDetailException) as exc_info:
        validate(ProductTable, {})
    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
    assert "name" in exc_info.value.detail


def test_validate_succeeds_with_required_columns() -> None:
    result = validate(ResourceTypeTable, {"resource_type": "some"})
    assert result == {"resource_type": "some"}


def test_validate_existing_instance_checks_pk() -> None:
    with pytest.raises(ProblemDetailException) as exc_info:
        validate(ResourceTypeTable, {"resource_type": "some"}, is_new_instance=False)
    assert "resource_type_id" in exc_info.value.detail


# --- transform_json ---


def test_transform_json_nests_product_blocks_and_resource_types() -> None:
    nested_body = {
        "name": "MSP",
        "description": "MSP",
        "product_type": "Port",
        "tag": "Port",
        "status": "active",
        "fixed_inputs": [{"name": "name", "value": "val"}],
        "product_blocks": [{"name": "name", "description": "desc", "resource_types": [{"resource_type": "test"}]}],
    }
    product = ProductTable(**transform_json(nested_body))
    assert product.product_blocks[0].resource_types[0].resource_type == "test"


# --- cleanse_json ---


@pytest.mark.parametrize(
    "input_dict,expected",
    [
        pytest.param({"a": 1, "b": None, "c": "keep"}, {"a": 1, "c": "keep"}, id="removes-none"),
        pytest.param({"name": "foo", "created_at": "2024-01-01"}, {"name": "foo"}, id="removes-created-at"),
        pytest.param({}, {}, id="empty-dict"),
    ],
)
def test_cleanse_json(input_dict: dict, expected: dict) -> None:
    cleanse_json(input_dict)
    assert input_dict == expected


def test_cleanse_json_recurses_into_lists() -> None:
    d = {"items": [{"x": 1, "created_at": "2024-01-01", "y": None}]}
    cleanse_json(d)
    assert d["items"][0] == {"x": 1}


# --- parse_date_fields ---


@pytest.mark.parametrize(
    "val",
    [
        pytest.param(1_700_000_000_000.0, id="float-ms"),
        pytest.param(1_700_000_000_000, id="int-ms"),
    ],
)
def test_parse_date_fields_numeric_timestamp(val: object) -> None:
    from datetime import datetime

    d: dict = {"end_date": val}
    parse_date_fields(d)
    assert isinstance(d["end_date"], datetime)


def test_parse_date_fields_iso_with_tz() -> None:
    d: dict = {"end_date": "2024-06-15T12:00:00+00:00"}
    parse_date_fields(d)
    assert d["end_date"].tzinfo is not None


def test_parse_date_fields_iso_without_tz_raises() -> None:
    with pytest.raises(AssertionError, match="timezone"):
        parse_date_fields({"end_date": "2024-06-15T12:00:00"})


# --- save / delete (integration with DB fixtures) ---


def test_delete_raises_not_found_for_missing_row(generic_resource_type_1) -> None:
    with pytest.raises(ProblemDetailException) as exc_info:
        delete(ResourceTypeTable, uuid4())
    assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


def test_delete_succeeds_for_existing_row(generic_resource_type_1) -> None:
    delete(ResourceTypeTable, generic_resource_type_1.resource_type_id)

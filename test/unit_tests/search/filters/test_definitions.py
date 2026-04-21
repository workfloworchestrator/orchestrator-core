"""Tests for orchestrator.search.filters.definitions: operators_for, value_schema_for, component_operators, and generate_definitions."""

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

import pytest

from orchestrator.core.search.core.types import FieldType, FilterOp, UIType
from orchestrator.core.search.filters.definitions import (
    TypeDefinition,
    component_operators,
    generate_definitions,
    operators_for,
    value_schema_for,
)

pytestmark = pytest.mark.search

_NUMERIC_OPS = [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE, FilterOp.BETWEEN]
_BOOLEAN_OPS = [FilterOp.EQ, FilterOp.NEQ]
_DATETIME_OPS = [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE, FilterOp.BETWEEN]
_STRING_OPS = [FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE]


# ---------------------------------------------------------------------------
# operators_for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_type, expected_ops",
    [
        pytest.param(FieldType.INTEGER, _NUMERIC_OPS, id="integer"),
        pytest.param(FieldType.FLOAT, _NUMERIC_OPS, id="float"),
        pytest.param(FieldType.BOOLEAN, _BOOLEAN_OPS, id="boolean"),
        pytest.param(FieldType.DATETIME, _DATETIME_OPS, id="datetime"),
        pytest.param(FieldType.STRING, _STRING_OPS, id="string"),
        pytest.param(FieldType.UUID, _STRING_OPS, id="uuid"),
        pytest.param(FieldType.BLOCK, _STRING_OPS, id="block"),
        pytest.param(FieldType.RESOURCE_TYPE, _STRING_OPS, id="resource_type"),
    ],
)
def test_operators_for_field_type(field_type: FieldType, expected_ops: list[FilterOp]) -> None:
    ops = operators_for(field_type)
    assert ops == expected_ops


@pytest.mark.parametrize(
    "field_type, expected_count",
    [
        pytest.param(FieldType.INTEGER, 7, id="integer"),
        pytest.param(FieldType.FLOAT, 7, id="float"),
        pytest.param(FieldType.BOOLEAN, 2, id="boolean"),
        pytest.param(FieldType.DATETIME, 7, id="datetime"),
        pytest.param(FieldType.STRING, 3, id="string"),
    ],
)
def test_operators_count(field_type: FieldType, expected_count: int) -> None:
    assert len(operators_for(field_type)) == expected_count


# ---------------------------------------------------------------------------
# value_schema_for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(FieldType.INTEGER, id="integer"),
        pytest.param(FieldType.FLOAT, id="float"),
    ],
)
def test_numeric_schema_has_seven_ops_with_between(field_type: FieldType) -> None:
    schema = value_schema_for(field_type)
    assert set(schema.keys()) == set(_NUMERIC_OPS)
    assert FilterOp.BETWEEN in schema


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(FieldType.INTEGER, id="integer"),
        pytest.param(FieldType.FLOAT, id="float"),
    ],
)
def test_numeric_between_schema_has_object_kind_with_fields(field_type: FieldType) -> None:
    schema = value_schema_for(field_type)
    between = schema[FilterOp.BETWEEN]
    assert between.kind == "object"
    assert between.fields is not None
    assert "start" in between.fields
    assert "end" in between.fields
    assert between.fields["start"].kind == UIType.NUMBER
    assert between.fields["end"].kind == UIType.NUMBER


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(FieldType.INTEGER, id="integer"),
        pytest.param(FieldType.FLOAT, id="float"),
    ],
)
def test_numeric_non_between_ops_have_number_kind(field_type: FieldType) -> None:
    schema = value_schema_for(field_type)
    for op in [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE]:
        assert schema[op].kind == UIType.NUMBER


def test_boolean_schema_has_two_ops() -> None:
    schema = value_schema_for(FieldType.BOOLEAN)
    assert set(schema.keys()) == {FilterOp.EQ, FilterOp.NEQ}
    assert schema[FilterOp.EQ].kind == UIType.BOOLEAN
    assert schema[FilterOp.NEQ].kind == UIType.BOOLEAN


def test_datetime_schema_has_seven_ops_with_between() -> None:
    schema = value_schema_for(FieldType.DATETIME)
    assert set(schema.keys()) == set(_DATETIME_OPS)
    assert FilterOp.BETWEEN in schema


def test_datetime_between_schema_has_datetime_fields() -> None:
    schema = value_schema_for(FieldType.DATETIME)
    between = schema[FilterOp.BETWEEN]
    assert between.kind == "object"
    assert between.fields is not None
    assert between.fields["start"].kind == UIType.DATETIME
    assert between.fields["end"].kind == UIType.DATETIME


def test_datetime_non_between_ops_have_datetime_kind() -> None:
    schema = value_schema_for(FieldType.DATETIME)
    for op in [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE]:
        assert schema[op].kind == UIType.DATETIME


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(FieldType.STRING, id="string"),
        pytest.param(FieldType.UUID, id="uuid"),
        pytest.param(FieldType.BLOCK, id="block"),
        pytest.param(FieldType.RESOURCE_TYPE, id="resource_type"),
    ],
)
def test_string_like_schema_has_three_ops_with_like(field_type: FieldType) -> None:
    schema = value_schema_for(field_type)
    assert set(schema.keys()) == {FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE}


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(FieldType.STRING, id="string"),
        pytest.param(FieldType.UUID, id="uuid"),
        pytest.param(FieldType.BLOCK, id="block"),
        pytest.param(FieldType.RESOURCE_TYPE, id="resource_type"),
    ],
)
def test_string_like_schema_ops_have_string_kind(field_type: FieldType) -> None:
    schema = value_schema_for(field_type)
    for op in [FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE]:
        assert schema[op].kind == UIType.STRING


# ---------------------------------------------------------------------------
# component_operators
# ---------------------------------------------------------------------------


def test_component_operators_returns_has_and_not_has() -> None:
    ops = component_operators()
    assert FilterOp.HAS_COMPONENT in ops
    assert FilterOp.NOT_HAS_COMPONENT in ops


def test_component_operators_both_have_component_ui_type() -> None:
    ops = component_operators()
    assert ops[FilterOp.HAS_COMPONENT].kind == UIType.COMPONENT
    assert ops[FilterOp.NOT_HAS_COMPONENT].kind == UIType.COMPONENT


def test_component_operators_exactly_two_entries() -> None:
    ops = component_operators()
    assert len(ops) == 2


# ---------------------------------------------------------------------------
# generate_definitions
# ---------------------------------------------------------------------------


def test_generate_definitions_all_ui_types_present() -> None:
    defs = generate_definitions()
    assert set(defs.keys()) == set(UIType)


def test_generate_definitions_all_values_are_type_definitions() -> None:
    defs = generate_definitions()
    assert all(isinstance(v, TypeDefinition) for v in defs.values())


def test_generate_definitions_component_has_component_ops() -> None:
    defs = generate_definitions()
    comp = defs[UIType.COMPONENT]
    assert FilterOp.HAS_COMPONENT in comp.operators
    assert FilterOp.NOT_HAS_COMPONENT in comp.operators
    assert len(comp.operators) == 2


@pytest.mark.parametrize(
    "ui_type, expected_ops",
    [
        pytest.param(UIType.NUMBER, set(_NUMERIC_OPS), id="number"),
        pytest.param(UIType.BOOLEAN, {FilterOp.EQ, FilterOp.NEQ}, id="boolean"),
        pytest.param(UIType.DATETIME, set(_DATETIME_OPS), id="datetime"),
        pytest.param(UIType.STRING, set(_STRING_OPS), id="string"),
    ],
)
def test_generate_definitions_ui_type_has_expected_ops(ui_type: UIType, expected_ops: set[FilterOp]) -> None:
    defs = generate_definitions()
    assert set(defs[ui_type].operators) == expected_ops


@pytest.mark.parametrize(
    "ui_type",
    [pytest.param(u, id=u.value) for u in UIType],
)
def test_generate_definitions_all_ui_types_have_non_empty_operators(ui_type: UIType) -> None:
    defs = generate_definitions()
    assert len(defs[ui_type].operators) > 0


@pytest.mark.parametrize(
    "ui_type",
    [pytest.param(u, id=u.value) for u in UIType],
)
def test_generate_definitions_operators_and_value_schema_keys_match(ui_type: UIType) -> None:
    defs = generate_definitions()
    td = defs[ui_type]
    assert set(td.operators) == set(td.value_schema.keys())

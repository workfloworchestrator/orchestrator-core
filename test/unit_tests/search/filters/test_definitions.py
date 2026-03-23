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

from orchestrator.search.core.types import FieldType, FilterOp, UIType
from orchestrator.search.filters.definitions import (
    TypeDefinition,
    ValueSchema,
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


class TestOperatorsFor:
    @pytest.mark.parametrize(
        "field_type, expected_ops",
        [
            (FieldType.INTEGER, _NUMERIC_OPS),
            (FieldType.FLOAT, _NUMERIC_OPS),
            (FieldType.BOOLEAN, _BOOLEAN_OPS),
            (FieldType.DATETIME, _DATETIME_OPS),
            (FieldType.STRING, _STRING_OPS),
            (FieldType.UUID, _STRING_OPS),
            (FieldType.BLOCK, _STRING_OPS),
            (FieldType.RESOURCE_TYPE, _STRING_OPS),
        ],
        ids=["integer", "float", "boolean", "datetime", "string", "uuid", "block", "resource_type"],
    )
    def test_operators_for_field_type(self, field_type: FieldType, expected_ops: list[FilterOp]) -> None:
        ops = operators_for(field_type)
        assert ops == expected_ops

    @pytest.mark.parametrize(
        "field_type, expected_count",
        [
            (FieldType.INTEGER, 7),
            (FieldType.FLOAT, 7),
            (FieldType.BOOLEAN, 2),
            (FieldType.DATETIME, 7),
            (FieldType.STRING, 3),
        ],
        ids=["integer-count", "float-count", "boolean-count", "datetime-count", "string-count"],
    )
    def test_operators_count(self, field_type: FieldType, expected_count: int) -> None:
        assert len(operators_for(field_type)) == expected_count


# ---------------------------------------------------------------------------
# value_schema_for
# ---------------------------------------------------------------------------


class TestValueSchemaFor:
    @pytest.mark.parametrize(
        "field_type",
        [FieldType.INTEGER, FieldType.FLOAT],
        ids=["integer", "float"],
    )
    def test_numeric_schema_has_seven_ops_with_between(self, field_type: FieldType) -> None:
        schema = value_schema_for(field_type)
        assert set(schema.keys()) == set(_NUMERIC_OPS)
        assert FilterOp.BETWEEN in schema

    @pytest.mark.parametrize(
        "field_type",
        [FieldType.INTEGER, FieldType.FLOAT],
        ids=["integer", "float"],
    )
    def test_numeric_between_schema_has_object_kind_with_fields(self, field_type: FieldType) -> None:
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
        [FieldType.INTEGER, FieldType.FLOAT],
        ids=["integer", "float"],
    )
    def test_numeric_non_between_ops_have_number_kind(self, field_type: FieldType) -> None:
        schema = value_schema_for(field_type)
        for op in [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE]:
            assert schema[op].kind == UIType.NUMBER

    def test_boolean_schema_has_two_ops(self) -> None:
        schema = value_schema_for(FieldType.BOOLEAN)
        assert set(schema.keys()) == {FilterOp.EQ, FilterOp.NEQ}
        assert schema[FilterOp.EQ].kind == UIType.BOOLEAN
        assert schema[FilterOp.NEQ].kind == UIType.BOOLEAN

    def test_datetime_schema_has_seven_ops_with_between(self) -> None:
        schema = value_schema_for(FieldType.DATETIME)
        assert set(schema.keys()) == set(_DATETIME_OPS)
        assert FilterOp.BETWEEN in schema

    def test_datetime_between_schema_has_datetime_fields(self) -> None:
        schema = value_schema_for(FieldType.DATETIME)
        between = schema[FilterOp.BETWEEN]
        assert between.kind == "object"
        assert between.fields is not None
        assert between.fields["start"].kind == UIType.DATETIME
        assert between.fields["end"].kind == UIType.DATETIME

    def test_datetime_non_between_ops_have_datetime_kind(self) -> None:
        schema = value_schema_for(FieldType.DATETIME)
        for op in [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE]:
            assert schema[op].kind == UIType.DATETIME

    @pytest.mark.parametrize(
        "field_type",
        [FieldType.STRING, FieldType.UUID, FieldType.BLOCK, FieldType.RESOURCE_TYPE],
        ids=["string", "uuid", "block", "resource_type"],
    )
    def test_string_like_schema_has_three_ops_with_like(self, field_type: FieldType) -> None:
        schema = value_schema_for(field_type)
        assert set(schema.keys()) == {FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE}

    @pytest.mark.parametrize(
        "field_type",
        [FieldType.STRING, FieldType.UUID, FieldType.BLOCK, FieldType.RESOURCE_TYPE],
        ids=["string", "uuid", "block", "resource_type"],
    )
    def test_string_like_schema_ops_have_string_kind(self, field_type: FieldType) -> None:
        schema = value_schema_for(field_type)
        for op in [FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE]:
            assert schema[op].kind == UIType.STRING


# ---------------------------------------------------------------------------
# component_operators
# ---------------------------------------------------------------------------


class TestComponentOperators:
    def test_returns_has_and_not_has_component(self) -> None:
        ops = component_operators()
        assert FilterOp.HAS_COMPONENT in ops
        assert FilterOp.NOT_HAS_COMPONENT in ops

    def test_both_ops_have_component_ui_type(self) -> None:
        ops = component_operators()
        assert ops[FilterOp.HAS_COMPONENT].kind == UIType.COMPONENT
        assert ops[FilterOp.NOT_HAS_COMPONENT].kind == UIType.COMPONENT

    def test_exactly_two_entries(self) -> None:
        ops = component_operators()
        assert len(ops) == 2

    def test_returns_value_schema_instances(self) -> None:
        ops = component_operators()
        assert all(isinstance(v, ValueSchema) for v in ops.values())


# ---------------------------------------------------------------------------
# generate_definitions
# ---------------------------------------------------------------------------


class TestGenerateDefinitions:
    def test_all_ui_types_are_present(self) -> None:
        defs = generate_definitions()
        assert set(defs.keys()) == set(UIType)

    def test_all_values_are_type_definition_instances(self) -> None:
        defs = generate_definitions()
        assert all(isinstance(v, TypeDefinition) for v in defs.values())

    def test_component_ui_type_has_component_ops(self) -> None:
        defs = generate_definitions()
        comp = defs[UIType.COMPONENT]
        assert FilterOp.HAS_COMPONENT in comp.operators
        assert FilterOp.NOT_HAS_COMPONENT in comp.operators
        assert len(comp.operators) == 2

    def test_number_ui_type_has_numeric_ops(self) -> None:
        defs = generate_definitions()
        num = defs[UIType.NUMBER]
        assert set(num.operators) == set(_NUMERIC_OPS)

    def test_boolean_ui_type_has_boolean_ops(self) -> None:
        defs = generate_definitions()
        bl = defs[UIType.BOOLEAN]
        assert set(bl.operators) == {FilterOp.EQ, FilterOp.NEQ}

    def test_datetime_ui_type_has_datetime_ops(self) -> None:
        defs = generate_definitions()
        dt = defs[UIType.DATETIME]
        assert set(dt.operators) == set(_DATETIME_OPS)

    def test_string_ui_type_has_string_ops(self) -> None:
        defs = generate_definitions()
        st = defs[UIType.STRING]
        assert set(st.operators) == set(_STRING_OPS)

    @pytest.mark.parametrize(
        "ui_type",
        list(UIType),
        ids=[u.value for u in UIType],
    )
    def test_all_ui_types_have_non_empty_operators(self, ui_type: UIType) -> None:
        defs = generate_definitions()
        assert len(defs[ui_type].operators) > 0

    @pytest.mark.parametrize(
        "ui_type",
        list(UIType),
        ids=[u.value for u in UIType],
    )
    def test_operators_and_value_schema_keys_match(self, ui_type: UIType) -> None:
        defs = generate_definitions()
        td = defs[ui_type]
        assert set(td.operators) == set(td.value_schema.keys())

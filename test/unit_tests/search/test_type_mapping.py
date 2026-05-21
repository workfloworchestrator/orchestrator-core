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

"""Tests for FieldType.from_type_hint: basic types, lists, unions, literals, annotated, enums, and edge cases."""

from datetime import datetime
from enum import Enum, IntEnum
from typing import Annotated, List, Literal, Union
from uuid import UUID

import pytest

from orchestrator.core.search.core.types import FieldType
from test.unit_tests.search.fixtures.blocks import MTU, MTUChoice, PriorityIntEnum, RequiredIntList, StatusEnum


@pytest.mark.parametrize(
    ("python_type", "expected_field_type"),
    [
        pytest.param(str, FieldType.STRING, id="str"),
        pytest.param(int, FieldType.INTEGER, id="int"),
        pytest.param(bool, FieldType.BOOLEAN, id="bool"),
        pytest.param(float, FieldType.FLOAT, id="float"),
        pytest.param(datetime, FieldType.DATETIME, id="datetime"),
        pytest.param(UUID, FieldType.UUID, id="uuid"),
        pytest.param(StatusEnum, FieldType.STRING, id="str-enum"),
        pytest.param(PriorityIntEnum, FieldType.INTEGER, id="int-enum"),
        pytest.param(List[int], FieldType.INTEGER, id="List-int"),
        pytest.param(list[int], FieldType.INTEGER, id="list-int"),
        pytest.param(list[float], FieldType.FLOAT, id="list-float"),
        pytest.param(list[bool], FieldType.BOOLEAN, id="list-bool"),
        pytest.param(list[StatusEnum], FieldType.STRING, id="list-str-enum"),
        pytest.param(list[PriorityIntEnum], FieldType.INTEGER, id="list-int-enum"),
        pytest.param(list[list[int]], FieldType.INTEGER, id="list-list-int"),
        pytest.param(list[str], FieldType.STRING, id="list-str"),
        pytest.param(int | None, FieldType.INTEGER, id="optional-int"),
        pytest.param(str | int, FieldType.STRING, id="union-str-int"),
        pytest.param(Union[int, None], FieldType.INTEGER, id="Union-int-None"),
        pytest.param(Union[str, int], FieldType.STRING, id="Union-str-int"),
        pytest.param(MTUChoice, FieldType.INTEGER, id="literal-int-mtu"),
        pytest.param(Literal[1500, 9000], FieldType.INTEGER, id="literal-int"),
        pytest.param(Literal["active", "inactive"], FieldType.STRING, id="literal-str"),
        pytest.param(Literal[True, False], FieldType.BOOLEAN, id="literal-bool"),
        pytest.param(Literal[1.5, 2.7], FieldType.FLOAT, id="literal-float"),
        pytest.param(MTU, FieldType.INTEGER, id="annotated-int-mtu"),
        pytest.param(RequiredIntList, FieldType.INTEGER, id="annotated-list-int"),
        pytest.param(Annotated[str, "constraint"], FieldType.STRING, id="annotated-str"),
        pytest.param(Annotated[float, "range"], FieldType.FLOAT, id="annotated-float"),
        pytest.param(Annotated[bool, "validator"], FieldType.BOOLEAN, id="annotated-bool"),
        pytest.param(Annotated[datetime, "timezone"], FieldType.DATETIME, id="annotated-datetime"),
        pytest.param(Annotated[UUID, "version"], FieldType.UUID, id="annotated-uuid"),
        pytest.param(Annotated[list[str], "min_length"], FieldType.STRING, id="annotated-list-str"),
        pytest.param(Annotated[Union[int, None], "optional"], FieldType.INTEGER, id="annotated-optional-int"),
        pytest.param(list[MTU], FieldType.INTEGER, id="list-annotated-mtu"),
        pytest.param(Union[MTU, None], FieldType.INTEGER, id="optional-annotated-mtu"),
        pytest.param(list, FieldType.STRING, id="bare-list-fallback"),
    ],
)
def test_type_mapping(python_type, expected_field_type):
    assert FieldType.from_type_hint(python_type) == expected_field_type


def test_unknown_type_defaults_to_string():
    class UnknownType:
        pass

    assert FieldType.from_type_hint(UnknownType) == FieldType.STRING


def test_product_block_model_returns_block():
    from orchestrator.core.domain.base import ProductBlockModel

    class TestBlock(ProductBlockModel):
        pass

    assert FieldType.from_type_hint(TestBlock) == FieldType.BLOCK


def test_enum_types():
    class TestStringEnum(Enum):
        VALUE1 = "value1"

    class TestIntEnum(IntEnum):
        VALUE1 = 1

    assert FieldType.from_type_hint(TestStringEnum) == FieldType.STRING
    assert FieldType.from_type_hint(TestIntEnum) == FieldType.INTEGER


@pytest.mark.parametrize(
    ("value", "expected_field_type"),
    [
        pytest.param("1000", FieldType.INTEGER, id="number-not-date"),
        pytest.param("42", FieldType.INTEGER, id="number-small"),
        pytest.param("10102026", FieldType.INTEGER, id="number-like-date"),
        pytest.param("3.14", FieldType.FLOAT, id="float-string"),
        pytest.param("true", FieldType.BOOLEAN, id="bool-true"),
        pytest.param("false", FieldType.BOOLEAN, id="bool-false"),
        pytest.param("2024-01-15", FieldType.DATETIME, id="iso-date"),
        pytest.param("2024-01-15T10:30:00", FieldType.DATETIME, id="iso-datetime"),
        pytest.param("hello", FieldType.STRING, id="plain-string"),
    ],
)
def test_infer_from_string_value(value, expected_field_type):
    assert FieldType.infer(value) == expected_field_type

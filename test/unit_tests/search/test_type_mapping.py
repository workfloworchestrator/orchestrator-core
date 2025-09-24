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
from typing import Annotated, List, Literal, Union
from uuid import UUID

import pytest

from orchestrator.search.core.types import FieldType

from .fixtures.blocks import MTU, MTUChoice, PriorityIntEnum, RequiredIntList, StatusEnum


class TestTypeMapping:
    """Test _type_hint_to_field_type handles all types used in our traversal fixtures."""

    @pytest.mark.parametrize(
        ("python_type", "expected_field_type"),
        [
            (str, FieldType.STRING),
            (int, FieldType.INTEGER),
            (bool, FieldType.BOOLEAN),
            (float, FieldType.FLOAT),
            (datetime, FieldType.DATETIME),
            (UUID, FieldType.UUID),
            (StatusEnum, FieldType.STRING),
            (PriorityIntEnum, FieldType.INTEGER),
        ],
    )
    def test_basic_type_mapping(self, python_type, expected_field_type):
        """Test direct Python type to FieldType mapping for all basic types in fixtures."""
        result = FieldType.from_type_hint(python_type)
        assert result == expected_field_type

    @pytest.mark.parametrize(
        ("list_type", "expected_field_type"),
        [
            (List[int], FieldType.INTEGER),
            (list[int], FieldType.INTEGER),
            (list[float], FieldType.FLOAT),
            (list[bool], FieldType.BOOLEAN),
            (list[StatusEnum], FieldType.STRING),
            (list[PriorityIntEnum], FieldType.INTEGER),
            (list[list[int]], FieldType.INTEGER),
            (list[str], FieldType.STRING),
        ],
    )
    def test_list_type_mapping(self, list_type, expected_field_type):
        """Test list types resolve to their element type for all list patterns in fixtures."""
        result = FieldType.from_type_hint(list_type)
        assert result == expected_field_type

    @pytest.mark.parametrize(
        ("union_type", "expected_field_type"),
        [
            (int | None, FieldType.INTEGER),  # optional_id
            (str | int, FieldType.STRING),  # id_or_name (takes first type)
            (Union[int, None], FieldType.INTEGER),
            (Union[str, int], FieldType.STRING),
        ],
    )
    def test_union_type_mapping(self, union_type, expected_field_type):
        """Test Union types resolve to first non-None type as used in UnionBlock."""
        result = FieldType.from_type_hint(union_type)
        assert result == expected_field_type

    @pytest.mark.parametrize(
        ("literal_type", "expected_field_type"),
        [
            (MTUChoice, FieldType.INTEGER),
            (Literal[1500, 9000], FieldType.INTEGER),
            (Literal["active", "inactive"], FieldType.STRING),
            (Literal[True, False], FieldType.BOOLEAN),
            (Literal[1.5, 2.7], FieldType.FLOAT),
        ],
    )
    def test_literal_type_mapping(self, literal_type, expected_field_type):
        """Test Literal types resolve based on their value types as used in fixtures."""
        result = FieldType.from_type_hint(literal_type)
        assert result == expected_field_type

    @pytest.mark.parametrize(
        ("annotated_type", "expected_field_type"),
        [
            (MTU, FieldType.INTEGER),  # Annotated[int, AfterValidator(validate_mtu)]
            (RequiredIntList, FieldType.INTEGER),  # Annotated[list[int], Len(min_length=1)]
            (Annotated[str, "constraint"], FieldType.STRING),
            (Annotated[float, "range"], FieldType.FLOAT),
            (Annotated[bool, "validator"], FieldType.BOOLEAN),
            (Annotated[datetime, "timezone"], FieldType.DATETIME),
            (Annotated[UUID, "version"], FieldType.UUID),
            (Annotated[list[str], "min_length"], FieldType.STRING),
            (Annotated[Union[int, None], "optional"], FieldType.INTEGER),
        ],
    )
    def test_annotated_type_mapping(self, annotated_type, expected_field_type):
        """Test Annotated types resolve to their inner type as used in fixtures."""
        result = FieldType.from_type_hint(annotated_type)
        assert result == expected_field_type

    def test_complex_nested_types_from_fixtures(self):
        """Test complex nested type combinations actually used in the fixtures."""

        result = FieldType.from_type_hint(list[MTU])
        assert result == FieldType.INTEGER

        result = FieldType.from_type_hint(Union[MTU, None])
        assert result == FieldType.INTEGER

    def test_unknown_type_defaults_to_string(self):
        """Test unknown types default to STRING."""

        class UnknownType:
            pass

        result = FieldType.from_type_hint(UnknownType)
        assert result == FieldType.STRING

    def test_list_edge_cases(self):
        """Test list edge cases that hit the string fallback."""
        result = FieldType.from_type_hint(list)
        assert result == FieldType.STRING

    def test_product_block_model_type(self):
        """Test ProductBlockModel returns BLOCK field type."""
        from orchestrator.domain.base import ProductBlockModel

        class TestBlock(ProductBlockModel):
            pass

        result = FieldType.from_type_hint(TestBlock)
        assert result == FieldType.BLOCK

    def test_enum_types(self):
        """Test enum type detection."""
        from enum import Enum, IntEnum

        class TestStringEnum(Enum):
            VALUE1 = "value1"
            VALUE2 = "value2"

        class TestIntEnum(IntEnum):
            VALUE1 = 1
            VALUE2 = 2

        result = FieldType.from_type_hint(TestStringEnum)
        assert result == FieldType.STRING

        result = FieldType.from_type_hint(TestIntEnum)
        assert result == FieldType.INTEGER

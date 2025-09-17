from typing import List, Union, Annotated, Literal
from datetime import datetime
from uuid import UUID

import pytest

from orchestrator.search.core.types import FieldType
from orchestrator.search.indexing.traverse import BaseTraverser
from .fixtures.blocks import StatusEnum, PriorityIntEnum, MTU, MTUChoice, RequiredIntList


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
        result = BaseTraverser._type_hint_to_field_type(python_type)
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
        result = BaseTraverser._type_hint_to_field_type(list_type)
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
        result = BaseTraverser._type_hint_to_field_type(union_type)
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
        result = BaseTraverser._type_hint_to_field_type(literal_type)
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
        result = BaseTraverser._type_hint_to_field_type(annotated_type)
        assert result == expected_field_type

    def test_complex_nested_types_from_fixtures(self):
        """Test complex nested type combinations actually used in the fixtures."""

        result = BaseTraverser._type_hint_to_field_type(list[MTU])
        assert result == FieldType.INTEGER

        result = BaseTraverser._type_hint_to_field_type(Union[MTU, None])
        assert result == FieldType.INTEGER

    def test_unknown_type_defaults_to_string(self):
        """Test unknown types default to STRING."""

        class UnknownType:
            pass

        result = BaseTraverser._type_hint_to_field_type(UnknownType)
        assert result == FieldType.STRING

    def test_list_edge_cases(self):
        """Test list edge cases that hit the string fallback."""
        result = BaseTraverser._type_hint_to_field_type(list)
        assert result == FieldType.STRING

    def test_product_block_model_type(self):
        """Test ProductBlockModel returns BLOCK field type."""
        from orchestrator.domain.base import ProductBlockModel

        class TestBlock(ProductBlockModel):
            pass

        result = BaseTraverser._type_hint_to_field_type(TestBlock)
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

        result = BaseTraverser._type_hint_to_field_type(TestStringEnum)
        assert result == FieldType.STRING

        result = BaseTraverser._type_hint_to_field_type(TestIntEnum)
        assert result == FieldType.INTEGER

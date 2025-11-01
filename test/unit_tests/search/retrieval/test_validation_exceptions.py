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

from unittest.mock import patch

import pytest

from orchestrator.search.core.types import BooleanOperator, EntityType, FieldType, FilterOp, UIType
from orchestrator.search.filters import (
    DateValueFilter,
    EqualityFilter,
    FilterTree,
    LtreeFilter,
    NumericValueFilter,
    PathFilter,
    StringFilter,
)
from orchestrator.search.query.exceptions import (
    EmptyFilterPathError,
    IncompatibleFilterTypeError,
    InvalidEntityPrefixError,
    InvalidLtreePatternError,
    PathNotFoundError,
)
from orchestrator.search.query.validation import (
    complete_filter_validation,
    is_filter_compatible_with_field_type,
    validate_filter_tree,
)


class TestFilterValidationExceptions:
    """Test that validation functions raise specific exceptions for agent feedback."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["", "   "])
    async def test_empty_filter_path_error(self, path):
        """Test that empty/whitespace filter paths raise EmptyFilterPathError."""
        filter_with_empty_path = PathFilter(
            path=path, condition=StringFilter(op=FilterOp.LIKE, value="%test%"), value_kind=UIType.STRING
        )

        with pytest.raises(EmptyFilterPathError):
            await complete_filter_validation(filter_with_empty_path, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_path_not_found_error(self, mock_validate_path):
        """Test that non-existent paths raise PathNotFoundError."""
        mock_validate_path.return_value = None

        filter_with_invalid_path = PathFilter(
            path="subscription.nonexistent.field",
            condition=StringFilter(op=FilterOp.LIKE, value="%test%"),
            value_kind=UIType.STRING,
        )

        with pytest.raises(PathNotFoundError):
            await complete_filter_validation(filter_with_invalid_path, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_incompatible_filter_type_error(self, mock_validate_path):
        """Test that incompatible filter types raise IncompatibleFilterTypeError."""
        mock_validate_path.return_value = FieldType.STRING.value

        filter_with_wrong_type = PathFilter(
            path="subscription.product.name",
            condition=NumericValueFilter(op=FilterOp.GT, value=123),
            value_kind=UIType.NUMBER,
        )

        with pytest.raises(IncompatibleFilterTypeError):
            await complete_filter_validation(filter_with_wrong_type, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_invalid_entity_prefix_error(self, mock_validate_path):
        """Test that wrong entity prefixes raise InvalidEntityPrefixError."""
        mock_validate_path.return_value = FieldType.STRING.value

        filter_with_wrong_prefix = PathFilter(
            path="workflow.name", condition=StringFilter(op=FilterOp.LIKE, value="%test%"), value_kind=UIType.STRING
        )

        with pytest.raises(InvalidEntityPrefixError):
            await complete_filter_validation(filter_with_wrong_prefix, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.is_lquery_syntactically_valid")
    async def test_invalid_ltree_pattern_error(self, mock_is_valid):
        """Test that invalid ltree patterns raise InvalidLtreePatternError."""
        mock_is_valid.return_value = False

        filter_with_invalid_ltree = PathFilter(
            path="subscription.path",
            condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="invalid[pattern"),
            value_kind=UIType.COMPONENT,
        )

        with pytest.raises(InvalidLtreePatternError):
            await complete_filter_validation(filter_with_invalid_ltree, EntityType.SUBSCRIPTION)


class TestFilterTreeValidation:
    """Test validation behavior for filter trees."""

    @pytest.mark.asyncio
    async def test_validate_filter_tree_with_none(self):
        """Test that validate_filter_tree handles None filters without error."""
        await validate_filter_tree(None, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_validate_filter_tree_propagates_exceptions(self, mock_validate_path):
        """Test that validate_filter_tree propagates specific exceptions from individual filters."""
        mock_validate_path.return_value = None

        invalid_filter = PathFilter(
            path="subscription.invalid.field",
            condition=StringFilter(op=FilterOp.LIKE, value="%test%"),
            value_kind=UIType.STRING,
        )
        filter_tree = FilterTree(op=BooleanOperator.AND, children=[invalid_filter])

        with pytest.raises(PathNotFoundError):
            await validate_filter_tree(filter_tree, EntityType.SUBSCRIPTION)


class TestFilterCompatibilityPaths:
    """Test successful validation paths for different filter types."""

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    @pytest.mark.parametrize(
        "field_type,filter_condition,value_kind",
        [
            (FieldType.STRING, StringFilter(op=FilterOp.LIKE, value="%test%"), UIType.STRING),
            (FieldType.BOOLEAN, EqualityFilter(op=FilterOp.EQ, value=True), UIType.BOOLEAN),
            (FieldType.DATETIME, DateValueFilter(op=FilterOp.EQ, value="2023-01-01"), UIType.DATETIME),
        ],
    )
    async def test_successful_filter_validation(self, mock_validate_path, field_type, filter_condition, value_kind):
        """Test that compatible filter types validate successfully."""
        mock_validate_path.return_value = field_type.value

        path_filter = PathFilter(
            path="subscription.test_field",
            condition=filter_condition,
            value_kind=value_kind,
        )

        await complete_filter_validation(path_filter, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_wildcard_path_bypasses_entity_prefix_check(self, mock_validate_path):
        """Test that wildcard paths ('*') bypass entity prefix validation."""
        mock_validate_path.return_value = FieldType.STRING.value

        filter_with_wildcard = PathFilter(
            path="*.name", condition=StringFilter(op=FilterOp.LIKE, value="%test%"), value_kind=UIType.STRING
        )

        await complete_filter_validation(filter_with_wildcard, EntityType.SUBSCRIPTION)
        mock_validate_path.assert_called_once_with("*.name")

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_ltree_filter_takes_special_path(self, mock_validate_path):
        """Test that LtreeFilter takes special validation path."""
        # mock_validate_path should not be called for LtreeFilter
        filter_with_ltree = PathFilter(
            path="subscription.path",
            condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.product.*"),
            value_kind=UIType.COMPONENT,
        )

        await complete_filter_validation(filter_with_ltree, EntityType.SUBSCRIPTION)
        mock_validate_path.assert_not_called()


class TestFilterTypeCompatibility:
    """Test the is_filter_compatible_with_field_type function directly."""

    def test_ltree_filter_always_returns_true(self):
        """Test that LtreeFilter compatibility always returns True for any field type."""
        ltree_filter = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.test.*")

        for field_type in FieldType:
            assert is_filter_compatible_with_field_type(ltree_filter, field_type) is True

    @pytest.mark.parametrize(
        "filter_type,compatible_fields,incompatible_fields",
        [
            (
                DateValueFilter(op=FilterOp.GT, value="2023-01-01"),
                [FieldType.DATETIME, FieldType.INTEGER, FieldType.FLOAT],
                [FieldType.STRING, FieldType.BOOLEAN],
            ),
            (
                NumericValueFilter(op=FilterOp.GT, value=123),
                [FieldType.INTEGER, FieldType.FLOAT, FieldType.DATETIME],
                [FieldType.STRING, FieldType.BOOLEAN],
            ),
            (
                StringFilter(op=FilterOp.LIKE, value="%test%"),
                [FieldType.STRING],
                [FieldType.INTEGER, FieldType.BOOLEAN, FieldType.DATETIME, FieldType.FLOAT],
            ),
            (
                EqualityFilter(op=FilterOp.EQ, value=True),
                [
                    FieldType.BOOLEAN,
                    FieldType.UUID,
                    FieldType.STRING,
                    FieldType.INTEGER,
                    FieldType.FLOAT,
                    FieldType.DATETIME,
                ],
                [],  # EQ operator is valid for all field types
            ),
        ],
    )
    def test_filter_compatibility_matrix(self, filter_type, compatible_fields, incompatible_fields):
        """Test filter compatibility with different field types."""
        for field_type in compatible_fields:
            assert is_filter_compatible_with_field_type(filter_type, field_type) is True

        for field_type in incompatible_fields:
            assert is_filter_compatible_with_field_type(filter_type, field_type) is False

    def test_unknown_filter_type_triggers_assert_never(self):
        """Test that unknown filter types trigger AttributeError."""

        class UnknownFilter:
            pass

        unknown_filter = UnknownFilter()

        with pytest.raises(AttributeError):
            is_filter_compatible_with_field_type(unknown_filter, FieldType.STRING)

"""Tests for search query validation and filter compatibility.

Covers exception raising for empty paths, missing paths, incompatible filter types,
invalid entity prefixes, invalid ltree patterns, filter tree validation, successful
validation paths, filter type compatibility matrix, and structured order_by validation.
"""

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

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.core.search.core.types import BooleanOperator, EntityType, FieldType, FilterOp, UIType
from orchestrator.core.search.filters import (
    DateValueFilter,
    EqualityFilter,
    FilterTree,
    LtreeFilter,
    NumericValueFilter,
    PathFilter,
    StringFilter,
)
from orchestrator.core.search.query.exceptions import (
    EmptyFilterPathError,
    IncompatibleFilterTypeError,
    InvalidEntityPrefixError,
    InvalidLtreePatternError,
    PathNotFoundError,
)
from orchestrator.core.search.query.validation import (
    complete_filter_validation,
    is_filter_compatible_with_field_type,
    validate_filter_tree,
    validate_structured_order_by_element,
)

# ---------------------------------------------------------------------------
# Filter validation exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("", id="empty_string"),
        pytest.param("   ", id="whitespace_only"),
    ],
)
async def test_empty_filter_path_raises_error(path):
    """Empty/whitespace filter paths raise EmptyFilterPathError."""
    filter_with_empty_path = PathFilter(
        path=path, condition=StringFilter(op=FilterOp.LIKE, value="%test%"), value_kind=UIType.STRING
    )
    with pytest.raises(EmptyFilterPathError):
        await complete_filter_validation(filter_with_empty_path, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_path_not_found_raises_error(mock_validate_path):
    """Non-existent paths raise PathNotFoundError."""
    mock_validate_path.return_value = None
    filter_with_invalid_path = PathFilter(
        path="subscription.nonexistent.field",
        condition=StringFilter(op=FilterOp.LIKE, value="%test%"),
        value_kind=UIType.STRING,
    )
    with pytest.raises(PathNotFoundError):
        await complete_filter_validation(filter_with_invalid_path, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_incompatible_filter_type_raises_error(mock_validate_path):
    """Incompatible filter types raise IncompatibleFilterTypeError."""
    mock_validate_path.return_value = FieldType.STRING.value
    filter_with_wrong_type = PathFilter(
        path="subscription.product.name",
        condition=NumericValueFilter(op=FilterOp.GT, value=123),
        value_kind=UIType.NUMBER,
    )
    with pytest.raises(IncompatibleFilterTypeError):
        await complete_filter_validation(filter_with_wrong_type, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_invalid_entity_prefix_raises_error(mock_validate_path):
    """Wrong entity prefixes raise InvalidEntityPrefixError."""
    mock_validate_path.return_value = FieldType.STRING.value
    filter_with_wrong_prefix = PathFilter(
        path="workflow.name", condition=StringFilter(op=FilterOp.LIKE, value="%test%"), value_kind=UIType.STRING
    )
    with pytest.raises(InvalidEntityPrefixError):
        await complete_filter_validation(filter_with_wrong_prefix, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.is_lquery_syntactically_valid")
async def test_invalid_ltree_pattern_raises_error(mock_is_valid):
    """Invalid ltree patterns raise InvalidLtreePatternError."""
    mock_is_valid.return_value = False
    filter_with_invalid_ltree = PathFilter(
        path="subscription.path",
        condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="invalid[pattern"),
        value_kind=UIType.COMPONENT,
    )
    with pytest.raises(InvalidLtreePatternError):
        await complete_filter_validation(filter_with_invalid_ltree, EntityType.SUBSCRIPTION)


# ---------------------------------------------------------------------------
# Filter tree validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_filter_tree_with_none():
    """validate_filter_tree handles None filters without error."""
    await validate_filter_tree(None, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_validate_filter_tree_propagates_exceptions(mock_validate_path):
    """validate_filter_tree propagates specific exceptions from individual filters."""
    mock_validate_path.return_value = None
    invalid_filter = PathFilter(
        path="subscription.invalid.field",
        condition=StringFilter(op=FilterOp.LIKE, value="%test%"),
        value_kind=UIType.STRING,
    )
    filter_tree = FilterTree(op=BooleanOperator.AND, children=[invalid_filter])
    with pytest.raises(PathNotFoundError):
        await validate_filter_tree(filter_tree, EntityType.SUBSCRIPTION)


# ---------------------------------------------------------------------------
# Successful filter validation paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
@pytest.mark.parametrize(
    "field_type,filter_condition,value_kind",
    [
        pytest.param(FieldType.STRING, StringFilter(op=FilterOp.LIKE, value="%test%"), UIType.STRING, id="string"),
        pytest.param(FieldType.BOOLEAN, EqualityFilter(op=FilterOp.EQ, value=True), UIType.BOOLEAN, id="boolean"),
        pytest.param(
            FieldType.DATETIME, DateValueFilter(op=FilterOp.EQ, value="2023-01-01"), UIType.DATETIME, id="datetime"
        ),
    ],
)
async def test_successful_filter_validation(mock_validate_path, field_type, filter_condition, value_kind):
    """Compatible filter types validate successfully without raising."""
    mock_validate_path.return_value = field_type.value
    path_filter = PathFilter(
        path="subscription.test_field",
        condition=filter_condition,
        value_kind=value_kind,
    )
    await complete_filter_validation(path_filter, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_wildcard_path_bypasses_entity_prefix_check(mock_validate_path):
    """Wildcard paths ('*') bypass entity prefix validation."""
    mock_validate_path.return_value = FieldType.STRING.value
    filter_with_wildcard = PathFilter(
        path="*.name", condition=StringFilter(op=FilterOp.LIKE, value="%test%"), value_kind=UIType.STRING
    )
    await complete_filter_validation(filter_with_wildcard, EntityType.SUBSCRIPTION)
    mock_validate_path.assert_called_once_with("*.name")


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.is_lquery_syntactically_valid", return_value=True)
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_ltree_filter_takes_special_path(mock_validate_path, mock_lquery_valid):
    """LtreeFilter takes special validation path and does not call validate_filter_path."""
    filter_with_ltree = PathFilter(
        path="subscription.path",
        condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.product.*"),
        value_kind=UIType.COMPONENT,
    )
    await complete_filter_validation(filter_with_ltree, EntityType.SUBSCRIPTION)
    mock_validate_path.assert_not_called()
    mock_lquery_valid.assert_called_once()


# ---------------------------------------------------------------------------
# Filter type compatibility
# ---------------------------------------------------------------------------


def test_ltree_filter_always_compatible():
    """LtreeFilter compatibility always returns True for any field type."""
    ltree_filter = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.test.*")
    for field_type in FieldType:
        assert is_filter_compatible_with_field_type(ltree_filter, field_type) is True


@pytest.mark.parametrize(
    "filter_obj,compatible_fields,incompatible_fields",
    [
        pytest.param(
            DateValueFilter(op=FilterOp.GT, value="2023-01-01"),
            [FieldType.DATETIME, FieldType.INTEGER, FieldType.FLOAT],
            [FieldType.STRING, FieldType.BOOLEAN],
            id="date_filter",
        ),
        pytest.param(
            NumericValueFilter(op=FilterOp.GT, value=123),
            [FieldType.INTEGER, FieldType.FLOAT, FieldType.DATETIME],
            [FieldType.STRING, FieldType.BOOLEAN],
            id="numeric_filter",
        ),
        pytest.param(
            StringFilter(op=FilterOp.LIKE, value="%test%"),
            [FieldType.STRING],
            [FieldType.INTEGER, FieldType.BOOLEAN, FieldType.DATETIME, FieldType.FLOAT],
            id="string_filter",
        ),
        pytest.param(
            EqualityFilter(op=FilterOp.EQ, value=True),
            [
                FieldType.BOOLEAN,
                FieldType.UUID,
                FieldType.STRING,
                FieldType.INTEGER,
                FieldType.FLOAT,
                FieldType.DATETIME,
            ],
            [],
            id="equality_filter_universal",
        ),
    ],
)
def test_filter_compatibility_matrix(filter_obj, compatible_fields, incompatible_fields):
    """Test filter compatibility with different field types."""
    for field_type in compatible_fields:
        assert is_filter_compatible_with_field_type(filter_obj, field_type) is True
    for field_type in incompatible_fields:
        assert is_filter_compatible_with_field_type(filter_obj, field_type) is False


def test_unknown_filter_type_triggers_attribute_error():
    """Unknown filter types trigger AttributeError."""

    class UnknownFilter:
        pass

    with pytest.raises(AttributeError):
        is_filter_compatible_with_field_type(UnknownFilter(), FieldType.STRING)


# ---------------------------------------------------------------------------
# Structured order_by validation
# ---------------------------------------------------------------------------


@patch("orchestrator.core.search.query.validation.get_ai_search_index_by_entity_type_and_path")
def test_validate_structured_order_by_element(mock_get_index):
    """Valid order_by element passes validation."""
    element = "subscription.element.not.exist"
    mock_get_index.return_value = {"path": element}
    request_mock = MagicMock()
    request_mock.order_by.element = element
    validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)


def test_validate_structured_order_by_element_without_request():
    """None request passes validation without error."""
    validate_structured_order_by_element(EntityType.SUBSCRIPTION, None)


@patch("orchestrator.core.search.query.validation.get_ai_search_index_by_entity_type_and_path")
def test_validate_structured_order_by_element_not_existing(mock_get_index):
    """Non-existent order_by element raises ValueError."""
    element = "subscription.element.not.exist"
    mock_get_index.return_value = None
    request_mock = MagicMock()
    request_mock.order_by.element = element
    with pytest.raises(ValueError, match=f"Element {element} is not a valid path"):
        validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)

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

"""Tests for orchestrator.core.search.query.validation -- filter compatibility, complete filter validation, aggregation/temporal/grouping/order-by field validation."""

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.core.search.aggregations import AggregationType
from orchestrator.core.search.core.types import EntityType, FieldType, FilterOp, UIType
from orchestrator.core.search.filters import (
    DateValueFilter,
    EqualityFilter,
    LtreeFilter,
    NumericValueFilter,
    PathFilter,
)
from orchestrator.core.search.query.exceptions import (
    EmptyFilterPathError,
    IncompatibleAggregationTypeError,
    IncompatibleFilterTypeError,
    IncompatibleTemporalGroupingTypeError,
    InvalidEntityPrefixError,
    PathNotFoundError,
)
from orchestrator.core.search.query.mixins import OrderBy, OrderDirection
from orchestrator.core.search.query.validation import (
    complete_filter_validation,
    is_filter_compatible_with_field_type,
    validate_aggregation_field,
    validate_grouping_fields,
    validate_order_by_fields,
    validate_structured_order_by_element,
    validate_temporal_grouping_field,
)

pytestmark = pytest.mark.search


# =============================================================================
# is_filter_compatible_with_field_type
# =============================================================================


@pytest.mark.parametrize("field_type", list(FieldType))
def test_ltree_filter_always_compatible(field_type: FieldType):
    """LtreeFilter is compatible with every FieldType."""
    ltree = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.test.*")
    assert is_filter_compatible_with_field_type(ltree, field_type) is True


@pytest.mark.parametrize(
    "filter_condition, field_type, expected",
    [
        pytest.param(EqualityFilter(op=FilterOp.EQ, value="foo"), FieldType.STRING, True, id="eq-string-valid"),
        pytest.param(EqualityFilter(op=FilterOp.NEQ, value="bar"), FieldType.STRING, True, id="neq-string-valid"),
        pytest.param(NumericValueFilter(op=FilterOp.GT, value=5), FieldType.INTEGER, True, id="gt-integer-valid"),
        pytest.param(NumericValueFilter(op=FilterOp.GT, value=5), FieldType.FLOAT, True, id="gt-float-valid"),
        pytest.param(NumericValueFilter(op=FilterOp.GT, value=5), FieldType.STRING, False, id="gt-string-invalid"),
        pytest.param(NumericValueFilter(op=FilterOp.GT, value=5), FieldType.BOOLEAN, False, id="gt-boolean-invalid"),
        pytest.param(
            DateValueFilter(op=FilterOp.LT, value="2025-01-01"), FieldType.DATETIME, True, id="lt-datetime-valid"
        ),
        pytest.param(
            DateValueFilter(op=FilterOp.LT, value="2025-01-01"), FieldType.STRING, False, id="lt-string-invalid"
        ),
        pytest.param(EqualityFilter(op=FilterOp.EQ, value=True), FieldType.BOOLEAN, True, id="eq-boolean-valid"),
        pytest.param(EqualityFilter(op=FilterOp.EQ, value=1), FieldType.INTEGER, True, id="eq-integer-valid"),
    ],
)
def test_filter_compatibility_matrix(filter_condition, field_type: FieldType, expected: bool):
    assert is_filter_compatible_with_field_type(filter_condition, field_type) is expected


# =============================================================================
# complete_filter_validation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
    ],
)
async def test_complete_filter_empty_path_raises(path: str):
    """Empty or whitespace-only path raises EmptyFilterPathError."""
    pf = PathFilter(
        path=path,
        condition=EqualityFilter(op=FilterOp.EQ, value="active"),
        value_kind=UIType.STRING,
    )
    with pytest.raises(EmptyFilterPathError):
        await complete_filter_validation(pf, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_complete_filter_path_not_found_raises(mock_vfp: MagicMock):
    """Path absent from index raises PathNotFoundError."""
    mock_vfp.return_value = None
    pf = PathFilter(
        path="subscription.nonexistent",
        condition=EqualityFilter(op=FilterOp.EQ, value="x"),
        value_kind=UIType.STRING,
    )
    with pytest.raises(PathNotFoundError):
        await complete_filter_validation(pf, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_complete_filter_incompatible_type_raises(mock_vfp: MagicMock):
    """Numeric operator on a string field raises IncompatibleFilterTypeError."""
    mock_vfp.return_value = FieldType.STRING.value
    pf = PathFilter(
        path="subscription.name",
        condition=NumericValueFilter(op=FilterOp.GT, value=10),
        value_kind=UIType.NUMBER,
    )
    with pytest.raises(IncompatibleFilterTypeError):
        await complete_filter_validation(pf, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_complete_filter_wrong_entity_prefix_raises(mock_vfp: MagicMock):
    """Path with wrong entity prefix raises InvalidEntityPrefixError."""
    mock_vfp.return_value = FieldType.STRING.value
    pf = PathFilter(
        path="workflow.name",
        condition=EqualityFilter(op=FilterOp.EQ, value="foo"),
        value_kind=UIType.STRING,
    )
    with pytest.raises(InvalidEntityPrefixError):
        await complete_filter_validation(pf, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_complete_filter_valid_path_passes(mock_vfp: MagicMock):
    """A correctly-typed path with the right entity prefix should not raise."""
    mock_vfp.return_value = FieldType.STRING.value
    pf = PathFilter(
        path="subscription.status",
        condition=EqualityFilter(op=FilterOp.EQ, value="active"),
        value_kind=UIType.STRING,
    )
    await complete_filter_validation(pf, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_complete_filter_wildcard_path_skips_prefix_check(mock_vfp: MagicMock):
    """Paths starting with '*' bypass the entity-prefix check."""
    mock_vfp.return_value = FieldType.STRING.value
    pf = PathFilter(
        path="*.name",
        condition=EqualityFilter(op=FilterOp.EQ, value="foo"),
        value_kind=UIType.STRING,
    )
    await complete_filter_validation(pf, EntityType.SUBSCRIPTION)


# =============================================================================
# validate_aggregation_field
# =============================================================================


AGGREGATION_TYPE_COMPATIBILITY_MATRIX = [
    pytest.param(AggregationType.SUM, FieldType.INTEGER, False, id="sum-integer-valid"),
    pytest.param(AggregationType.SUM, FieldType.FLOAT, False, id="sum-float-valid"),
    pytest.param(AggregationType.SUM, FieldType.STRING, True, id="sum-string-invalid"),
    pytest.param(AggregationType.SUM, FieldType.BOOLEAN, True, id="sum-boolean-invalid"),
    pytest.param(AggregationType.SUM, FieldType.DATETIME, True, id="sum-datetime-invalid"),
    pytest.param(AggregationType.AVG, FieldType.INTEGER, False, id="avg-integer-valid"),
    pytest.param(AggregationType.AVG, FieldType.FLOAT, False, id="avg-float-valid"),
    pytest.param(AggregationType.AVG, FieldType.STRING, True, id="avg-string-invalid"),
    pytest.param(AggregationType.MIN, FieldType.INTEGER, False, id="min-integer-valid"),
    pytest.param(AggregationType.MIN, FieldType.FLOAT, False, id="min-float-valid"),
    pytest.param(AggregationType.MIN, FieldType.DATETIME, False, id="min-datetime-valid"),
    pytest.param(AggregationType.MIN, FieldType.STRING, True, id="min-string-invalid"),
    pytest.param(AggregationType.MAX, FieldType.INTEGER, False, id="max-integer-valid"),
    pytest.param(AggregationType.MAX, FieldType.FLOAT, False, id="max-float-valid"),
    pytest.param(AggregationType.MAX, FieldType.DATETIME, False, id="max-datetime-valid"),
    pytest.param(AggregationType.MAX, FieldType.STRING, True, id="max-string-invalid"),
]


@pytest.mark.parametrize("agg_type, field_type, should_raise", AGGREGATION_TYPE_COMPATIBILITY_MATRIX)
@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_aggregation_field_compatibility(
    mock_vfp: MagicMock, agg_type: AggregationType, field_type: FieldType, should_raise: bool
):
    mock_vfp.return_value = field_type.value
    if should_raise:
        with pytest.raises(IncompatibleAggregationTypeError):
            validate_aggregation_field(agg_type, "subscription.field")
    else:
        validate_aggregation_field(agg_type, "subscription.field")


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_aggregation_field_path_not_found_raises(mock_vfp: MagicMock):
    mock_vfp.return_value = None
    with pytest.raises(PathNotFoundError):
        validate_aggregation_field(AggregationType.SUM, "subscription.missing")


# =============================================================================
# validate_temporal_grouping_field
# =============================================================================


TEMPORAL_GROUPING_FIELD_TYPE_MATRIX = [
    pytest.param(FieldType.DATETIME, False, id="datetime-valid"),
    pytest.param(FieldType.STRING, True, id="string-invalid"),
    pytest.param(FieldType.INTEGER, True, id="integer-invalid"),
    pytest.param(FieldType.FLOAT, True, id="float-invalid"),
    pytest.param(FieldType.BOOLEAN, True, id="boolean-invalid"),
]


@pytest.mark.parametrize("field_type, should_raise", TEMPORAL_GROUPING_FIELD_TYPE_MATRIX)
@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_temporal_grouping_field_type_matrix(mock_vfp: MagicMock, field_type: FieldType, should_raise: bool):
    mock_vfp.return_value = field_type.value
    if should_raise:
        with pytest.raises(IncompatibleTemporalGroupingTypeError):
            validate_temporal_grouping_field("subscription.some_field")
    else:
        validate_temporal_grouping_field("subscription.some_field")


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_temporal_grouping_field_path_not_found_raises(mock_vfp: MagicMock):
    mock_vfp.return_value = None
    with pytest.raises(PathNotFoundError):
        validate_temporal_grouping_field("subscription.missing")


# =============================================================================
# validate_grouping_fields
# =============================================================================


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_grouping_fields_all_paths_found_passes(mock_vfp: MagicMock):
    mock_vfp.return_value = FieldType.STRING.value
    validate_grouping_fields(["subscription.status", "subscription.product.name"])


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_grouping_fields_one_path_not_found_raises(mock_vfp: MagicMock):
    mock_vfp.side_effect = [FieldType.STRING.value, None]
    with pytest.raises(PathNotFoundError):
        validate_grouping_fields(["subscription.status", "subscription.missing"])


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_grouping_fields_empty_list_passes(mock_vfp: MagicMock):
    validate_grouping_fields([])
    mock_vfp.assert_not_called()


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_grouping_fields_single_path_not_found_raises(mock_vfp: MagicMock):
    mock_vfp.return_value = None
    with pytest.raises(PathNotFoundError):
        validate_grouping_fields(["subscription.nonexistent"])


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_grouping_fields_validates_each_path_once(mock_vfp: MagicMock):
    mock_vfp.return_value = FieldType.STRING.value
    paths = ["subscription.status", "subscription.product.name", "subscription.start_date"]
    validate_grouping_fields(paths)
    assert mock_vfp.call_count == len(paths)


# =============================================================================
# validate_order_by_fields
# =============================================================================


def test_validate_order_by_fields_none_passes():
    """None order_by should return immediately without error."""
    validate_order_by_fields(None)


def test_validate_order_by_fields_empty_list_passes():
    validate_order_by_fields([])


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_order_by_fields_path_with_dot_found_passes(mock_vfp: MagicMock):
    mock_vfp.return_value = FieldType.STRING.value
    validate_order_by_fields([OrderBy(field="subscription.status", direction=OrderDirection.ASC)])


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_order_by_fields_path_with_dot_not_found_raises(mock_vfp: MagicMock):
    mock_vfp.return_value = None
    with pytest.raises(PathNotFoundError):
        validate_order_by_fields([OrderBy(field="subscription.missing", direction=OrderDirection.DESC)])


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_order_by_fields_alias_without_dot_skipped(mock_vfp: MagicMock):
    """Aggregation aliases (no dot) are skipped and validate_filter_path is not called."""
    validate_order_by_fields([OrderBy(field="count", direction=OrderDirection.DESC)])
    mock_vfp.assert_not_called()


@patch("orchestrator.core.search.query.validation.validate_filter_path")
def test_validate_order_by_fields_mixed_alias_and_path(mock_vfp: MagicMock):
    """Aliases are skipped; only path-based fields are validated."""
    mock_vfp.return_value = FieldType.STRING.value
    order_by = [
        OrderBy(field="count"),
        OrderBy(field="subscription.status"),
        OrderBy(field="revenue"),
    ]
    validate_order_by_fields(order_by)
    mock_vfp.assert_called_once_with("subscription.status")


# =============================================================================
# validate_structured_order_by_element
# =============================================================================


def test_validate_structured_order_by_element_none_request_passes():
    """None request returns early without error."""
    validate_structured_order_by_element(EntityType.SUBSCRIPTION, None)


@patch("orchestrator.core.search.query.validation.get_ai_search_index_by_entity_type_and_path")
def test_validate_structured_order_by_element_valid_passes(mock_get: MagicMock):
    mock_get.return_value = {"path": "subscription.status"}
    request_mock = MagicMock()
    request_mock.order_by.element = "subscription.status"
    validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)


@patch("orchestrator.core.search.query.validation.get_ai_search_index_by_entity_type_and_path")
def test_validate_structured_order_by_element_invalid_raises(mock_get: MagicMock):
    element = "subscription.nonexistent"
    mock_get.return_value = None
    request_mock = MagicMock()
    request_mock.order_by.element = element
    with pytest.raises(ValueError, match=f"Element {element} is not a valid path"):
        validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)


def test_validate_structured_order_by_element_none_entity_type_skips():
    """entity_type=None means validation is skipped even with a request."""
    request_mock = MagicMock()
    request_mock.order_by.element = "subscription.status"
    validate_structured_order_by_element(None, request_mock)


@patch("orchestrator.core.search.query.validation.get_ai_search_index_by_entity_type_and_path")
def test_validate_structured_order_by_element_no_order_by_passes(mock_get: MagicMock):
    """Request with order_by=None should not trigger validation."""
    request_mock = MagicMock()
    request_mock.order_by = None
    validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)
    mock_get.assert_not_called()

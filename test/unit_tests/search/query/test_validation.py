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

from orchestrator.search.aggregations import AggregationType
from orchestrator.search.core.types import EntityType, FieldType, FilterOp, UIType
from orchestrator.search.filters import DateValueFilter, EqualityFilter, LtreeFilter, NumericValueFilter, PathFilter
from orchestrator.search.query.exceptions import (
    EmptyFilterPathError,
    IncompatibleAggregationTypeError,
    IncompatibleFilterTypeError,
    IncompatibleTemporalGroupingTypeError,
    InvalidEntityPrefixError,
    InvalidLtreePatternError,
    PathNotFoundError,
)
from orchestrator.search.query.mixins import OrderBy, OrderDirection
from orchestrator.search.query.validation import (
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


class TestIsFilterCompatibleWithFieldType:
    """Tests for is_filter_compatible_with_field_type."""

    @pytest.mark.parametrize("field_type", list(FieldType))
    def test_ltree_filter_always_compatible(self, field_type: FieldType) -> None:
        """LtreeFilter is compatible with every FieldType."""
        ltree = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.test.*")
        assert is_filter_compatible_with_field_type(ltree, field_type) is True

    @pytest.mark.parametrize(
        "filter_condition, field_type, expected",
        [
            # EQ on STRING is valid
            (EqualityFilter(op=FilterOp.EQ, value="foo"), FieldType.STRING, True),
            # NEQ on STRING is valid
            (EqualityFilter(op=FilterOp.NEQ, value="bar"), FieldType.STRING, True),
            # GT on INTEGER is valid
            (NumericValueFilter(op=FilterOp.GT, value=5), FieldType.INTEGER, True),
            # GT on FLOAT is valid
            (NumericValueFilter(op=FilterOp.GT, value=5), FieldType.FLOAT, True),
            # GT on STRING is invalid (GT not in STRING operators)
            (NumericValueFilter(op=FilterOp.GT, value=5), FieldType.STRING, False),
            # GT on BOOLEAN is invalid
            (NumericValueFilter(op=FilterOp.GT, value=5), FieldType.BOOLEAN, False),
            # LT date on DATETIME is valid
            (DateValueFilter(op=FilterOp.LT, value="2025-01-01"), FieldType.DATETIME, True),
            # LT date on STRING is invalid
            (DateValueFilter(op=FilterOp.LT, value="2025-01-01"), FieldType.STRING, False),
            # EQ on BOOLEAN is valid
            (EqualityFilter(op=FilterOp.EQ, value=True), FieldType.BOOLEAN, True),
            # EQ on INTEGER is valid (EQ is in all operator sets)
            (EqualityFilter(op=FilterOp.EQ, value=1), FieldType.INTEGER, True),
        ],
        ids=[
            "eq-string-valid",
            "neq-string-valid",
            "gt-integer-valid",
            "gt-float-valid",
            "gt-string-invalid",
            "gt-boolean-invalid",
            "lt-datetime-valid",
            "lt-string-invalid",
            "eq-boolean-valid",
            "eq-integer-valid",
        ],
    )
    def test_compatibility_matrix(self, filter_condition, field_type: FieldType, expected: bool) -> None:
        assert is_filter_compatible_with_field_type(filter_condition, field_type) is expected


# =============================================================================
# complete_filter_validation
# =============================================================================


class TestCompleteFilterValidation:
    """Tests for the async complete_filter_validation function."""

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.is_lquery_syntactically_valid")
    async def test_ltree_filter_valid_syntax_passes(self, mock_is_valid: MagicMock) -> None:
        """LtreeFilter with valid syntax should not raise."""
        mock_is_valid.return_value = True
        pf = PathFilter(
            path="subscription.path",
            condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.valid.*"),
            value_kind=UIType.COMPONENT,
        )
        await complete_filter_validation(pf, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.is_lquery_syntactically_valid")
    async def test_ltree_filter_invalid_syntax_raises(self, mock_is_valid: MagicMock) -> None:
        """LtreeFilter with invalid syntax raises InvalidLtreePatternError."""
        mock_is_valid.return_value = False
        pf = PathFilter(
            path="subscription.path",
            condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="invalid[pattern"),
            value_kind=UIType.COMPONENT,
        )
        with pytest.raises(InvalidLtreePatternError):
            await complete_filter_validation(pf, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["", "   "])
    async def test_empty_path_raises(self, path: str) -> None:
        """Empty or whitespace-only path raises EmptyFilterPathError."""
        pf = PathFilter(
            path=path,
            condition=EqualityFilter(op=FilterOp.EQ, value="active"),
            value_kind=UIType.STRING,
        )
        with pytest.raises(EmptyFilterPathError):
            await complete_filter_validation(pf, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_path_not_found_raises(self, mock_vfp: MagicMock) -> None:
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
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_incompatible_type_raises(self, mock_vfp: MagicMock) -> None:
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
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_wrong_entity_prefix_raises(self, mock_vfp: MagicMock) -> None:
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
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_valid_path_passes(self, mock_vfp: MagicMock) -> None:
        """A correctly-typed path with the right entity prefix should not raise."""
        mock_vfp.return_value = FieldType.STRING.value
        pf = PathFilter(
            path="subscription.status",
            condition=EqualityFilter(op=FilterOp.EQ, value="active"),
            value_kind=UIType.STRING,
        )
        await complete_filter_validation(pf, EntityType.SUBSCRIPTION)

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.validation.validate_filter_path")
    async def test_wildcard_path_skips_prefix_check(self, mock_vfp: MagicMock) -> None:
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


class TestValidateAggregationField:
    """Tests for validate_aggregation_field."""

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_sum_on_integer_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.INTEGER.value
        validate_aggregation_field(AggregationType.SUM, "subscription.price")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_sum_on_float_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.FLOAT.value
        validate_aggregation_field(AggregationType.SUM, "subscription.ratio")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_avg_on_integer_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.INTEGER.value
        validate_aggregation_field(AggregationType.AVG, "subscription.count")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_sum_on_string_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.STRING.value
        with pytest.raises(IncompatibleAggregationTypeError):
            validate_aggregation_field(AggregationType.SUM, "subscription.name")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_avg_on_string_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.STRING.value
        with pytest.raises(IncompatibleAggregationTypeError):
            validate_aggregation_field(AggregationType.AVG, "subscription.name")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_path_not_found_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = None
        with pytest.raises(PathNotFoundError):
            validate_aggregation_field(AggregationType.SUM, "subscription.missing")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_min_on_datetime_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.DATETIME.value
        validate_aggregation_field(AggregationType.MIN, "subscription.start_date")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_max_on_float_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.FLOAT.value
        validate_aggregation_field(AggregationType.MAX, "subscription.ratio")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_min_on_string_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.STRING.value
        with pytest.raises(IncompatibleAggregationTypeError):
            validate_aggregation_field(AggregationType.MIN, "subscription.name")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_max_on_boolean_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.BOOLEAN.value
        with pytest.raises(IncompatibleAggregationTypeError):
            validate_aggregation_field(AggregationType.MAX, "subscription.active")

    @pytest.mark.parametrize(
        "agg_type, field_type, should_raise",
        [
            (AggregationType.SUM, FieldType.INTEGER, False),
            (AggregationType.SUM, FieldType.FLOAT, False),
            (AggregationType.SUM, FieldType.STRING, True),
            (AggregationType.SUM, FieldType.BOOLEAN, True),
            (AggregationType.SUM, FieldType.DATETIME, True),
            (AggregationType.AVG, FieldType.INTEGER, False),
            (AggregationType.AVG, FieldType.FLOAT, False),
            (AggregationType.AVG, FieldType.STRING, True),
            (AggregationType.MIN, FieldType.INTEGER, False),
            (AggregationType.MIN, FieldType.FLOAT, False),
            (AggregationType.MIN, FieldType.DATETIME, False),
            (AggregationType.MIN, FieldType.STRING, True),
            (AggregationType.MAX, FieldType.INTEGER, False),
            (AggregationType.MAX, FieldType.FLOAT, False),
            (AggregationType.MAX, FieldType.DATETIME, False),
            (AggregationType.MAX, FieldType.STRING, True),
        ],
    )
    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_aggregation_type_compatibility_matrix(
        self, mock_vfp: MagicMock, agg_type: AggregationType, field_type: FieldType, should_raise: bool
    ) -> None:
        mock_vfp.return_value = field_type.value
        if should_raise:
            with pytest.raises(IncompatibleAggregationTypeError):
                validate_aggregation_field(agg_type, "subscription.field")
        else:
            validate_aggregation_field(agg_type, "subscription.field")


# =============================================================================
# validate_temporal_grouping_field
# =============================================================================


class TestValidateTemporalGroupingField:
    """Tests for validate_temporal_grouping_field."""

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_datetime_field_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.DATETIME.value
        validate_temporal_grouping_field("subscription.start_date")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_non_datetime_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.STRING.value
        with pytest.raises(IncompatibleTemporalGroupingTypeError):
            validate_temporal_grouping_field("subscription.name")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_integer_field_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.INTEGER.value
        with pytest.raises(IncompatibleTemporalGroupingTypeError):
            validate_temporal_grouping_field("subscription.count")

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_path_not_found_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = None
        with pytest.raises(PathNotFoundError):
            validate_temporal_grouping_field("subscription.missing")

    @pytest.mark.parametrize(
        "field_type, should_raise",
        [
            (FieldType.DATETIME, False),
            (FieldType.STRING, True),
            (FieldType.INTEGER, True),
            (FieldType.FLOAT, True),
            (FieldType.BOOLEAN, True),
        ],
    )
    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_temporal_grouping_field_type_matrix(
        self, mock_vfp: MagicMock, field_type: FieldType, should_raise: bool
    ) -> None:
        mock_vfp.return_value = field_type.value
        if should_raise:
            with pytest.raises(IncompatibleTemporalGroupingTypeError):
                validate_temporal_grouping_field("subscription.some_field")
        else:
            validate_temporal_grouping_field("subscription.some_field")


# =============================================================================
# validate_grouping_fields
# =============================================================================


class TestValidateGroupingFields:
    """Tests for validate_grouping_fields."""

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_all_paths_found_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.STRING.value
        validate_grouping_fields(["subscription.status", "subscription.product.name"])

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_one_path_not_found_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.side_effect = [FieldType.STRING.value, None]
        with pytest.raises(PathNotFoundError):
            validate_grouping_fields(["subscription.status", "subscription.missing"])

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_empty_list_passes(self, mock_vfp: MagicMock) -> None:
        validate_grouping_fields([])
        mock_vfp.assert_not_called()

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_single_path_not_found_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = None
        with pytest.raises(PathNotFoundError):
            validate_grouping_fields(["subscription.nonexistent"])

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_all_paths_validates_each_once(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.STRING.value
        paths = ["subscription.status", "subscription.product.name", "subscription.start_date"]
        validate_grouping_fields(paths)
        assert mock_vfp.call_count == len(paths)


# =============================================================================
# validate_order_by_fields
# =============================================================================


class TestValidateOrderByFields:
    """Tests for validate_order_by_fields."""

    def test_none_passes(self) -> None:
        """None order_by should return immediately without error."""
        validate_order_by_fields(None)

    def test_empty_list_passes(self) -> None:
        validate_order_by_fields([])

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_path_with_dot_found_passes(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = FieldType.STRING.value
        validate_order_by_fields([OrderBy(field="subscription.status", direction=OrderDirection.ASC)])

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_path_with_dot_not_found_raises(self, mock_vfp: MagicMock) -> None:
        mock_vfp.return_value = None
        with pytest.raises(PathNotFoundError):
            validate_order_by_fields([OrderBy(field="subscription.missing", direction=OrderDirection.DESC)])

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_alias_without_dot_skipped(self, mock_vfp: MagicMock) -> None:
        """Aggregation aliases (no dot) are skipped and validate_filter_path is not called."""
        validate_order_by_fields([OrderBy(field="count", direction=OrderDirection.DESC)])
        mock_vfp.assert_not_called()

    @patch("orchestrator.search.query.validation.validate_filter_path")
    def test_mixed_alias_and_path(self, mock_vfp: MagicMock) -> None:
        """Aliases are skipped; only path-based fields are validated."""
        mock_vfp.return_value = FieldType.STRING.value
        order_by = [
            OrderBy(field="count"),
            OrderBy(field="subscription.status"),
            OrderBy(field="revenue"),
        ]
        validate_order_by_fields(order_by)
        # Only the path field should trigger a db lookup
        mock_vfp.assert_called_once_with("subscription.status")


# =============================================================================
# validate_structured_order_by_element
# =============================================================================


class TestValidateStructuredOrderByElement:
    """Tests for validate_structured_order_by_element."""

    def test_none_request_passes(self) -> None:
        """None request returns early without error."""
        validate_structured_order_by_element(EntityType.SUBSCRIPTION, None)

    @patch("orchestrator.search.query.validation.get_ai_search_index_by_entity_type_and_path")
    def test_valid_element_passes(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {"path": "subscription.status"}
        request_mock = MagicMock()
        request_mock.order_by.element = "subscription.status"
        validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)

    @patch("orchestrator.search.query.validation.get_ai_search_index_by_entity_type_and_path")
    def test_invalid_element_raises(self, mock_get: MagicMock) -> None:
        element = "subscription.nonexistent"
        mock_get.return_value = None
        request_mock = MagicMock()
        request_mock.order_by.element = element
        with pytest.raises(ValueError, match=f"Element {element} is not a valid path"):
            validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)

    def test_none_entity_type_with_request_skips_validation(self) -> None:
        """entity_type=None means validation is skipped even with a request."""
        request_mock = MagicMock()
        request_mock.order_by.element = "subscription.status"
        # Should not raise even though no DB lookup is made
        validate_structured_order_by_element(None, request_mock)

    @patch("orchestrator.search.query.validation.get_ai_search_index_by_entity_type_and_path")
    def test_request_without_order_by_passes(self, mock_get: MagicMock) -> None:
        """Request with order_by=None should not trigger validation."""
        request_mock = MagicMock()
        request_mock.order_by = None
        validate_structured_order_by_element(EntityType.SUBSCRIPTION, request_mock)
        mock_get.assert_not_called()

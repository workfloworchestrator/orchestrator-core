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

from unittest.mock import MagicMock

import pytest

from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, LtreeFilter, PathFilter
from orchestrator.search.query.queries import CountQuery
from orchestrator.search.query.results import (
    MatchingField,
    QueryResultsResponse,
    ResultRow,
    _extract_matching_field_from_filters,
    format_aggregation_response,
    truncate_text_with_highlights,
)

pytestmark = pytest.mark.search


# =============================================================================
# Helpers
# =============================================================================


def _make_row_mapping(data: dict) -> MagicMock:
    """Create a RowMapping-like mock that supports .items()."""
    mock = MagicMock()
    mock.items.return_value = list(data.items())
    return mock


def _single_leaf_filter_tree(condition, path: str = "subscription.status") -> FilterTree:
    return FilterTree(
        op=BooleanOperator.AND,
        children=[PathFilter(path=path, condition=condition, value_kind=UIType.STRING)],
    )


# =============================================================================
# truncate_text_with_highlights
# =============================================================================


class TestTruncateTextWithHighlights:
    """Tests for truncate_text_with_highlights."""

    def test_short_text_returned_unchanged(self) -> None:
        """Text shorter than max_length is returned as-is."""
        text = "Hello world"
        result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=None)
        assert result_text == text
        assert result_indices is None

    def test_short_text_with_highlights_returned_unchanged(self) -> None:
        """Short text with highlights preserves both text and highlight indices."""
        text = "Hello world"
        indices = [(0, 5)]
        result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=indices)
        assert result_text == text
        assert result_indices == indices

    def test_long_text_no_highlights_truncated_from_beginning(self) -> None:
        """Long text without highlights is truncated from the start and gets '...' suffix."""
        text = "A" * 600
        result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=None, max_length=500)
        assert len(result_text) == 503  # 500 + len("...")
        assert result_text.endswith("...")
        assert result_indices is None

    def test_long_text_exact_max_length_no_suffix(self) -> None:
        """Text of exactly max_length returns unchanged (no '...')."""
        text = "B" * 500
        result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=None, max_length=500)
        assert result_text == text
        assert not result_text.endswith("...")

    def test_highlight_in_middle_gets_ellipsis_on_both_sides(self) -> None:
        """Highlight in middle of long text should add '...' prefix and suffix."""
        text = "X" * 600
        # Put highlight at position 300 (middle)
        indices = [(300, 310)]
        result_text, result_indices = truncate_text_with_highlights(
            text, highlight_indices=indices, max_length=100, context_chars=10
        )
        assert result_text.startswith("...")
        assert result_text.endswith("...")
        assert result_indices is not None

    def test_highlight_at_start_no_leading_ellipsis(self) -> None:
        """Highlight near the beginning of text should not add leading '...'."""
        text = "Hello " + "X" * 600
        indices = [(0, 5)]
        result_text, result_indices = truncate_text_with_highlights(
            text, highlight_indices=indices, max_length=200, context_chars=0
        )
        assert not result_text.startswith("...")

    def test_highlight_near_end_no_trailing_ellipsis(self) -> None:
        """Highlight near the end of text should not add trailing '...'."""
        text = "X" * 600 + " end"
        highlight_start = len(text) - 4  # 'end'
        indices = [(highlight_start, len(text))]
        result_text, result_indices = truncate_text_with_highlights(
            text, highlight_indices=indices, max_length=500, context_chars=100
        )
        assert not result_text.endswith("...")

    def test_highlight_indices_adjusted_for_offset(self) -> None:
        """Adjusted highlight indices must be non-negative and within truncated text."""
        text = "A" * 200 + "HIGHLIGHT" + "B" * 400
        hl_start = 200
        hl_end = 209
        indices = [(hl_start, hl_end)]
        result_text, result_indices = truncate_text_with_highlights(
            text, highlight_indices=indices, max_length=100, context_chars=20
        )
        assert result_indices is not None
        for start, end in result_indices:
            assert start >= 0
            assert end <= len(result_text)

    @pytest.mark.parametrize(
        "max_length, context_chars",
        [
            (50, 10),
            (100, 20),
            (200, 50),
        ],
    )
    def test_custom_max_length_and_context(self, max_length: int, context_chars: int) -> None:
        """Custom max_length and context_chars produce consistent results."""
        text = "X" * 1000
        indices = [(500, 510)]
        result_text, _ = truncate_text_with_highlights(
            text, highlight_indices=indices, max_length=max_length, context_chars=context_chars
        )
        # The returned text (excluding '...') should not exceed max_length
        core_text = result_text.removeprefix("...").removesuffix("...")
        assert len(core_text) <= max_length

    def test_out_of_range_highlights_excluded(self) -> None:
        """Highlights outside the truncated window are dropped (returns None)."""
        text = "A" * 1000
        # Highlight far from the truncation window chosen by context
        # context = 10 -> start = max(0, 500-10) = 490, end = 590 (max_length=100)
        # Put second highlight at 900 which is outside [490, 590]
        indices = [(500, 510), (900, 910)]
        _, result_indices = truncate_text_with_highlights(
            text, highlight_indices=indices, max_length=100, context_chars=10
        )
        if result_indices is not None:
            for _hl_start, hl_end in result_indices:
                assert hl_end <= len(text)


# =============================================================================
# format_aggregation_response
# =============================================================================


class TestFormatAggregationResponse:
    """Tests for format_aggregation_response."""

    def _make_count_query(self) -> CountQuery:
        return CountQuery(entity_type=EntityType.SUBSCRIPTION, group_by=["subscription.status"])

    def test_single_row_with_group_and_aggregation(self) -> None:
        query = self._make_count_query()
        row = _make_row_mapping({"subscription.status": "active", "count": 42})
        result = format_aggregation_response([row], ["subscription.status"], query)

        assert isinstance(result, QueryResultsResponse)
        assert len(result.results) == 1
        assert result.results[0].group_values == {"subscription.status": "active"}
        assert result.results[0].aggregations == {"count": 42}

    def test_none_aggregation_value_defaults_to_zero(self) -> None:
        query = self._make_count_query()
        row = _make_row_mapping({"subscription.status": "active", "count": None})
        result = format_aggregation_response([row], ["subscription.status"], query)

        assert result.results[0].aggregations["count"] == 0

    def test_none_group_value_defaults_to_empty_string(self) -> None:
        query = self._make_count_query()
        row = _make_row_mapping({"subscription.status": None, "count": 5})
        result = format_aggregation_response([row], ["subscription.status"], query)

        assert result.results[0].group_values["subscription.status"] == ""

    def test_empty_result_rows(self) -> None:
        query = self._make_count_query()
        result = format_aggregation_response([], ["subscription.status"], query)

        assert result.results == []
        assert result.total_results == 0

    def test_multiple_rows(self) -> None:
        query = self._make_count_query()
        rows = [
            _make_row_mapping({"subscription.status": "active", "count": 10}),
            _make_row_mapping({"subscription.status": "terminated", "count": 5}),
        ]
        result = format_aggregation_response(rows, ["subscription.status"], query)

        assert len(result.results) == 2
        assert result.total_results == 2

    def test_total_results_matches_row_count(self) -> None:
        query = self._make_count_query()
        rows = [_make_row_mapping({"subscription.status": f"status_{i}", "count": i}) for i in range(7)]
        result = format_aggregation_response(rows, ["subscription.status"], query)

        assert result.total_results == 7

    def test_metadata_search_type_is_aggregation(self) -> None:
        query = self._make_count_query()
        result = format_aggregation_response([], ["subscription.status"], query)

        assert result.metadata.search_type == "aggregation"

    def test_non_group_column_goes_to_aggregations(self) -> None:
        query = CountQuery(entity_type=EntityType.SUBSCRIPTION, group_by=["subscription.status"])
        row = _make_row_mapping({"subscription.status": "active", "total_price": 100.5})
        result = format_aggregation_response([row], ["subscription.status"], query)

        assert "total_price" in result.results[0].aggregations
        assert "total_price" not in result.results[0].group_values

    def test_result_row_is_result_row_type(self) -> None:
        query = self._make_count_query()
        row = _make_row_mapping({"subscription.status": "active", "count": 1})
        result = format_aggregation_response([row], ["subscription.status"], query)

        assert all(isinstance(r, ResultRow) for r in result.results)


# =============================================================================
# _extract_matching_field_from_filters
# =============================================================================


class TestExtractMatchingFieldFromFilters:
    """Tests for _extract_matching_field_from_filters."""

    def test_single_equality_filter_returns_matching_field(self) -> None:
        """Single leaf with EqualityFilter returns a MatchingField with the filter value."""
        tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value="active"))
        result = _extract_matching_field_from_filters(tree)

        assert isinstance(result, MatchingField)
        assert result.text == "active"
        assert result.path == "subscription.status"
        assert result.highlight_indices == [(0, len("active"))]

    def test_single_equality_filter_none_value_returns_empty_text(self) -> None:
        """EqualityFilter with None value produces empty text."""
        tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value=None))
        result = _extract_matching_field_from_filters(tree)

        assert isinstance(result, MatchingField)
        assert result.text == ""

    def test_ltree_has_component_returns_matching_field(self) -> None:
        """LtreeFilter with HAS_COMPONENT returns a MatchingField with the component as text."""
        # has_component with explicit value (path is set to '*' by model_validator)
        tree = FilterTree(
            op=BooleanOperator.AND,
            children=[
                PathFilter(
                    path="subscription",
                    condition=LtreeFilter(op=FilterOp.HAS_COMPONENT, value="node"),
                    value_kind=UIType.COMPONENT,
                )
            ],
        )
        result = _extract_matching_field_from_filters(tree)

        assert isinstance(result, MatchingField)
        assert result.text == "node"

    def test_ltree_not_has_component_returns_none(self) -> None:
        """LtreeFilter with NOT_HAS_COMPONENT returns None (absence cannot be highlighted)."""
        tree = FilterTree(
            op=BooleanOperator.AND,
            children=[
                PathFilter(
                    path="subscription",
                    condition=LtreeFilter(op=FilterOp.NOT_HAS_COMPONENT, value="node"),
                    value_kind=UIType.COMPONENT,
                )
            ],
        )
        result = _extract_matching_field_from_filters(tree)

        assert result is None

    def test_multiple_leaves_returns_none(self) -> None:
        """Multiple leaves in the filter tree returns None."""
        tree = FilterTree(
            op=BooleanOperator.AND,
            children=[
                PathFilter(
                    path="subscription.status",
                    condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                    value_kind=UIType.STRING,
                ),
                PathFilter(
                    path="subscription.name",
                    condition=EqualityFilter(op=FilterOp.EQ, value="test"),
                    value_kind=UIType.STRING,
                ),
            ],
        )
        result = _extract_matching_field_from_filters(tree)

        assert result is None

    def test_ltree_matches_lquery_returns_matching_field(self) -> None:
        """LtreeFilter with MATCHES_LQUERY (not NOT_HAS_COMPONENT) returns MatchingField."""
        tree = FilterTree(
            op=BooleanOperator.AND,
            children=[
                PathFilter(
                    path="subscription.path",
                    condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.product.*"),
                    value_kind=UIType.COMPONENT,
                )
            ],
        )
        result = _extract_matching_field_from_filters(tree)

        assert isinstance(result, MatchingField)

    @pytest.mark.parametrize(
        "value, expected_text",
        [
            ("active", "active"),
            ("terminated", "terminated"),
            ("", ""),
            (42, "42"),
        ],
        ids=["active", "terminated", "empty", "numeric"],
    )
    def test_equality_filter_value_becomes_text(self, value, expected_text: str) -> None:
        tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value=value))
        result = _extract_matching_field_from_filters(tree)

        assert isinstance(result, MatchingField)
        assert result.text == expected_text
        assert result.highlight_indices == [(0, len(expected_text))]

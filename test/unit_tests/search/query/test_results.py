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

"""Tests for orchestrator.core.search.query.results -- text truncation with highlights, aggregation response formatting, and filter field extraction."""

from unittest.mock import MagicMock

import pytest

from orchestrator.core.search.core.types import BooleanOperator, EntityType, FilterOp, SearchMetadata, UIType
from orchestrator.core.search.filters import ContainsFilter, EqualityFilter, FilterTree, LtreeFilter, PathFilter
from orchestrator.core.search.query.queries import CountQuery, SelectQuery
from orchestrator.core.search.query.results import (
    MatchingField,
    QueryResultsResponse,
    ResultRow,
    _resolve_structured_matching_fields,
    format_aggregation_response,
    format_search_response,
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


def _make_count_query() -> CountQuery:
    return CountQuery(entity_type=EntityType.SUBSCRIPTION, group_by=["subscription.status"])


# =============================================================================
# truncate_text_with_highlights
# =============================================================================


def test_truncate_short_text_returned_unchanged():
    """Text shorter than max_length is returned as-is."""
    text = "Hello world"
    result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=None)
    assert result_text == text
    assert result_indices is None


def test_truncate_short_text_with_highlights_returned_unchanged():
    """Short text with highlights preserves both text and highlight indices."""
    text = "Hello world"
    indices = [(0, 5)]
    result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=indices)
    assert result_text == text
    assert result_indices == indices


def test_truncate_long_text_no_highlights_truncated_from_beginning():
    """Long text without highlights is truncated from the start and gets '...' suffix."""
    text = "A" * 600
    result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=None, max_length=500)
    assert len(result_text) == 503  # 500 + len("...")
    assert result_text.endswith("...")
    assert result_indices is None


def test_truncate_long_text_exact_max_length_no_suffix():
    """Text of exactly max_length returns unchanged (no '...')."""
    text = "B" * 500
    result_text, result_indices = truncate_text_with_highlights(text, highlight_indices=None, max_length=500)
    assert result_text == text
    assert not result_text.endswith("...")


def test_truncate_highlight_in_middle_gets_ellipsis_on_both_sides():
    """Highlight in middle of long text should add '...' prefix and suffix."""
    text = "X" * 600
    indices = [(300, 310)]
    result_text, result_indices = truncate_text_with_highlights(
        text, highlight_indices=indices, max_length=100, context_chars=10
    )
    assert result_text.startswith("...")
    assert result_text.endswith("...")
    assert result_indices is not None


def test_truncate_highlight_at_start_no_leading_ellipsis():
    """Highlight near the beginning of text should not add leading '...'."""
    text = "Hello " + "X" * 600
    indices = [(0, 5)]
    result_text, result_indices = truncate_text_with_highlights(
        text, highlight_indices=indices, max_length=200, context_chars=0
    )
    assert not result_text.startswith("...")


def test_truncate_highlight_near_end_no_trailing_ellipsis():
    """Highlight near the end of text should not add trailing '...'."""
    text = "X" * 600 + " end"
    highlight_start = len(text) - 4
    indices = [(highlight_start, len(text))]
    result_text, result_indices = truncate_text_with_highlights(
        text, highlight_indices=indices, max_length=500, context_chars=100
    )
    assert not result_text.endswith("...")


def test_truncate_highlight_indices_adjusted_for_offset():
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
        pytest.param(50, 10, id="small"),
        pytest.param(100, 20, id="medium"),
        pytest.param(200, 50, id="large"),
    ],
)
def test_truncate_custom_max_length_and_context(max_length: int, context_chars: int):
    """Custom max_length and context_chars produce consistent results."""
    text = "X" * 1000
    indices = [(500, 510)]
    result_text, _ = truncate_text_with_highlights(
        text, highlight_indices=indices, max_length=max_length, context_chars=context_chars
    )
    core_text = result_text.removeprefix("...").removesuffix("...")
    assert len(core_text) <= max_length


@pytest.mark.parametrize(
    "indices",
    [
        pytest.param([(500, 510)], id="single-highlight-in-window"),
        pytest.param([(500, 510), (900, 910)], id="second-highlight-out-of-window"),
    ],
)
def test_truncate_out_of_range_highlights_excluded(indices: list[tuple[int, int]]):
    """Highlights outside the truncated window are dropped or clamped to text bounds."""
    text = "A" * 1000
    _, result_indices = truncate_text_with_highlights(text, highlight_indices=indices, max_length=100, context_chars=10)
    if result_indices is not None:
        for _hl_start, hl_end in result_indices:
            assert hl_end <= len(text)


# =============================================================================
# format_aggregation_response
# =============================================================================


def test_format_aggregation_single_row_with_group_and_aggregation():
    query = _make_count_query()
    row = _make_row_mapping({"subscription.status": "active", "count": 42})
    result = format_aggregation_response([row], ["subscription.status"], query)

    assert isinstance(result, QueryResultsResponse)
    assert len(result.results) == 1
    assert result.results[0].group_values == {"subscription.status": "active"}
    assert result.results[0].aggregations == {"count": 42}


def test_format_aggregation_none_value_defaults_to_zero():
    query = _make_count_query()
    row = _make_row_mapping({"subscription.status": "active", "count": None})
    result = format_aggregation_response([row], ["subscription.status"], query)
    assert result.results[0].aggregations["count"] == 0


def test_format_aggregation_none_group_value_defaults_to_empty_string():
    query = _make_count_query()
    row = _make_row_mapping({"subscription.status": None, "count": 5})
    result = format_aggregation_response([row], ["subscription.status"], query)
    assert result.results[0].group_values["subscription.status"] == ""


def test_format_aggregation_empty_result_rows():
    query = _make_count_query()
    result = format_aggregation_response([], ["subscription.status"], query)
    assert result.results == []
    assert result.total_results == 0


def test_format_aggregation_multiple_rows():
    query = _make_count_query()
    rows = [
        _make_row_mapping({"subscription.status": "active", "count": 10}),
        _make_row_mapping({"subscription.status": "terminated", "count": 5}),
    ]
    result = format_aggregation_response(rows, ["subscription.status"], query)
    assert len(result.results) == 2
    assert result.total_results == 2


def test_format_aggregation_total_results_matches_row_count():
    query = _make_count_query()
    rows = [_make_row_mapping({"subscription.status": f"status_{i}", "count": i}) for i in range(7)]
    result = format_aggregation_response(rows, ["subscription.status"], query)
    assert result.total_results == 7


def test_format_aggregation_metadata_search_type_is_aggregation():
    query = _make_count_query()
    result = format_aggregation_response([], ["subscription.status"], query)
    assert result.metadata.search_type == "aggregation"


def test_format_aggregation_non_group_column_goes_to_aggregations():
    query = CountQuery(entity_type=EntityType.SUBSCRIPTION, group_by=["subscription.status"])
    row = _make_row_mapping({"subscription.status": "active", "total_price": 100.5})
    result = format_aggregation_response([row], ["subscription.status"], query)
    assert "total_price" in result.results[0].aggregations
    assert "total_price" not in result.results[0].group_values


def test_format_aggregation_result_row_type():
    query = _make_count_query()
    row = _make_row_mapping({"subscription.status": "active", "count": 1})
    result = format_aggregation_response([row], ["subscription.status"], query)
    assert all(isinstance(r, ResultRow) for r in result.results)


# =============================================================================
# _resolve_structured_matching_fields
# =============================================================================


def _row_with_highlights(pairs: list[tuple[str, str]]) -> MagicMock:
    """Build a mock row carrying the aggregated highlight_matches JSON column.

    Each pair is a single match for its leaf (one inner array per leaf).
    For multi-match-per-leaf scenarios, build the nested structure directly.
    """
    matches = [[{"value": text, "path": path, "idx": i}] for i, (text, path) in enumerate(pairs)]
    data: dict[str, list] = {"highlight_matches": matches} if matches else {}
    mock = MagicMock()
    mock.get = data.get
    return mock


def test_resolve_single_equality_filter():
    """Single leaf with EqualityFilter returns one MatchingField from DB columns."""
    tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value="active"))
    row = _row_with_highlights([("active", "subscription.status")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 1
    assert result[0].text == "active"
    assert result[0].path == "subscription.status"
    assert result[0].highlight_indices == [(0, len("active"))]


def test_resolve_missing_highlight_columns_returns_empty():
    """When the row has no highlight columns, returns empty list."""
    tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value="active"))
    row = MagicMock()
    row.get = {}.get
    result = _resolve_structured_matching_fields(row, tree)
    assert result == []


def test_resolve_ltree_has_component():
    """LtreeFilter with HAS_COMPONENT returns one MatchingField from DB columns."""
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
    row = _row_with_highlights([("node", "subscription.node")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 1
    assert result[0].text == "node"


def test_resolve_ltree_not_has_component_returns_empty():
    """NOT_HAS_COMPONENT is excluded from positive leaves — returns empty."""
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
    row = _row_with_highlights([])
    result = _resolve_structured_matching_fields(row, tree)
    assert result == []


def test_resolve_multiple_leaves():
    """Multiple positive leaves each produce a MatchingField."""
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
    row = _row_with_highlights([("active", "subscription.status"), ("test", "subscription.name")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 2
    assert result[0].path == "subscription.status"
    assert result[0].text == "active"
    assert result[1].path == "subscription.name"
    assert result[1].text == "test"


def test_resolve_not_has_component_excluded_from_indexing():
    """NOT_HAS_COMPONENT leaf is excluded; only the EQ leaf is indexed at position 0."""
    tree = FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="subscription.status",
                condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            ),
            PathFilter(
                path="subscription",
                condition=LtreeFilter(op=FilterOp.NOT_HAS_COMPONENT, value="node"),
                value_kind=UIType.COMPONENT,
            ),
        ],
    )
    row = _row_with_highlights([("active", "subscription.status")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 1
    assert result[0].path == "subscription.status"


def test_resolve_ltree_matches_lquery():
    """LtreeFilter with MATCHES_LQUERY returns one MatchingField."""
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
    row = _row_with_highlights([("product", "subscription.path.product")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 1
    assert isinstance(result[0], MatchingField)


@pytest.mark.parametrize(
    "value, expected_text",
    [
        pytest.param("active", "active", id="active"),
        pytest.param("terminated", "terminated", id="terminated"),
        pytest.param("", "", id="empty"),
        pytest.param(42, "42", id="numeric"),
    ],
)
def test_resolve_equality_filter_value_highlighted(value, expected_text: str):
    tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value=value))
    row = _row_with_highlights([(str(value) if value is not None else "", "subscription.status")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 1
    assert isinstance(result[0], MatchingField)
    assert result[0].text == expected_text
    assert result[0].highlight_indices == [(0, len(expected_text))]


def test_resolve_neq_filter_returns_null_highlight_indices():
    """NEQ filter returns the stored value as context but highlight_indices=None (no term to highlight)."""
    tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.NEQ, value="terminated"))
    row = _row_with_highlights([("active", "subscription.status")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 1
    assert result[0].text == "active"
    assert result[0].path == "subscription.status"
    assert result[0].highlight_indices is None


def test_resolve_not_contains_filter_returns_null_highlight_indices():
    """NOT_CONTAINS filter returns the stored value as context but highlight_indices=None."""
    tree = _single_leaf_filter_tree(ContainsFilter(op=FilterOp.NOT_CONTAINS, value="fiber"))
    row = _row_with_highlights([("Corelink 10G", "subscription.description")])
    result = _resolve_structured_matching_fields(row, tree)
    assert len(result) == 1
    assert result[0].text == "Corelink 10G"
    assert result[0].highlight_indices is None


# =============================================================================
# format_search_response — structured search matching_field
# =============================================================================


class _StubRow:
    """Minimal RowMapping stand-in supporting attribute access and .get()."""

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def get(self, key, default=None):
        return self._data.get(key, default)


def _structured_query(filters: FilterTree) -> SelectQuery:
    return SelectQuery(entity_type=EntityType.SUBSCRIPTION, filters=filters)


def _structured_row(**extra) -> _StubRow:
    return _StubRow({"entity_id": "e-1", "entity_title": "sub", "score": 1.0, **extra})


def test_format_structured_response_uses_highlight_columns_for_full_path():
    """Structured rows carrying highlight columns report the resolved full path and stored value."""
    tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value="active"), path="status")
    row = _structured_row(highlight_matches=[[{"value": "active", "path": "subscription.status", "idx": 0}]])

    response = format_search_response(
        [row], _structured_query(tree), SearchMetadata.structured(), None, None, None, None
    )

    fields = response.results[0].matching_fields
    assert len(fields) == 1
    assert fields[0].path == "subscription.status"
    assert fields[0].text == "active"
    assert fields[0].highlight_indices == [(0, len("active"))]


def test_format_structured_response_highlights_full_text_when_value_not_in_text():
    """When the filter term does not occur in the stored value, the whole value is highlighted."""
    tree = FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="*",
                condition=LtreeFilter(op=FilterOp.ENDS_WITH, value="status"),
                value_kind=UIType.COMPONENT,
            )
        ],
    )
    row = _structured_row(highlight_matches=[[{"value": "active", "path": "subscription.status", "idx": 0}]])

    response = format_search_response(
        [row], _structured_query(tree), SearchMetadata.structured(), None, None, None, None
    )

    fields = response.results[0].matching_fields
    assert len(fields) == 1
    assert fields[0].path == "subscription.status"
    assert fields[0].text == "active"
    assert fields[0].highlight_indices == [(0, len("active"))]


def test_format_structured_response_without_highlight_columns_returns_empty():
    """Structured rows without highlight columns return no matching fields."""
    tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value="active"), path="subscription.status")
    row = _structured_row()

    response = format_search_response(
        [row], _structured_query(tree), SearchMetadata.structured(), None, None, None, None
    )

    assert response.results[0].matching_fields == []


def test_resolve_multiple_matches_per_leaf():
    """A global filter matching multiple index rows returns all of them.

    E.g. ``status = 'active'`` (no dot, matches any path ending in 'status') hitting
    both ``product.status`` and ``product_block.test.status`` on the same entity.
    """
    tree = _single_leaf_filter_tree(EqualityFilter(op=FilterOp.EQ, value="active"), path="status")
    matches = [
        [
            {"value": "active", "path": "product.status", "idx": 0},
            {"value": "active", "path": "product_block.test.status", "idx": 0},
        ]
    ]
    mock = MagicMock()
    mock.get = {"highlight_matches": matches}.get
    result = _resolve_structured_matching_fields(mock, tree)

    assert len(result) == 2
    paths = {r.path for r in result}
    assert paths == {"product.status", "product_block.test.status"}
    assert all(r.text == "active" for r in result)
    assert all(r.highlight_indices == [(0, len("active"))] for r in result)

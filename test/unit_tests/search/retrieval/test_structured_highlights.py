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

"""Tests for the StructuredRetriever highlight-matches column SQL.

Value-filter leaves aggregate every matching index row (json_agg), while
path-predicate leaves (has_component, ends_with, ...) return a single
representative row: the shallowest matching path.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.core.search.filters import FilterTree, PathFilter
from orchestrator.core.search.filters.base import EqualityFilter
from orchestrator.core.search.filters.ltree_filters import LtreeFilter
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.retrievers.structured import StructuredRetriever


def _compile(filters: FilterTree | None) -> str:
    candidate = select(
        AiSearchIndex.entity_id.label("entity_id"), AiSearchIndex.entity_title.label("entity_title")
    ).distinct()
    query = StructuredRetriever(cursor=None, filters=filters).apply(candidate)
    return str(query.compile(dialect=postgresql.dialect()))


def _component_leaf(op: FilterOp, value: str = "port") -> PathFilter:
    return PathFilter(path="*", condition=LtreeFilter(op=op, value=value), value_kind=UIType.COMPONENT)  # type: ignore[arg-type]


def _value_leaf() -> PathFilter:
    return PathFilter(
        path="subscription.status",
        condition=EqualityFilter(op=FilterOp.EQ, value="active"),
        value_kind=UIType.STRING,
    )


def test_ends_with_leaf_selects_single_representative_row() -> None:
    """ends_with matches leaf fields, so the row's own value and full path are reported."""
    filters = FilterTree(op=BooleanOperator.AND, children=[_component_leaf(FilterOp.ENDS_WITH, value="status")])
    sql = _compile(filters)
    assert "nlevel" in sql
    assert "LIMIT" in sql
    assert "subltree" not in sql
    assert "json_agg" not in sql


def test_value_leaf_aggregates_all_matching_rows() -> None:
    filters = FilterTree(op=BooleanOperator.AND, children=[_value_leaf()])
    sql = _compile(filters)
    assert "json_agg" in sql
    assert "nlevel" not in sql
    assert "LIMIT" not in sql


def test_mixed_value_and_ends_with_leaves_use_both_strategies() -> None:
    filters = FilterTree(
        op=BooleanOperator.AND, children=[_value_leaf(), _component_leaf(FilterOp.ENDS_WITH, value="status")]
    )
    sql = _compile(filters)
    assert "json_agg" in sql
    assert "nlevel" in sql


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(FilterOp.HAS_COMPONENT, id="has-component"),
        pytest.param(FilterOp.NOT_HAS_COMPONENT, id="not-has-component"),
    ],
)
def test_component_existence_leaf_produces_no_highlight_column(op: FilterOp) -> None:
    """Existence filters are satisfied by every result (or by absence) — nothing to highlight."""
    filters = FilterTree(op=BooleanOperator.AND, children=[_component_leaf(op)])
    sql = _compile(filters)
    assert Retriever.HIGHLIGHT_MATCHES_LABEL not in sql


def test_mixed_value_and_has_component_highlights_value_leaf_only() -> None:
    filters = FilterTree(op=BooleanOperator.AND, children=[_value_leaf(), _component_leaf(FilterOp.HAS_COMPONENT)])
    sql = _compile(filters)
    assert "json_agg" in sql
    assert "nlevel" not in sql
    assert "LIMIT" not in sql


def test_no_filters_produces_no_highlight_column() -> None:
    sql = _compile(None)
    assert Retriever.HIGHLIGHT_MATCHES_LABEL not in sql

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

"""Tests that component-existence filters produce no highlight-matches column.

`has_component` / `not_has_component` are satisfied by every result (or by absence),
so there is nothing to report; the StructuredRetriever must omit the column entirely.
What the column contains for other filter leaves is covered end-to-end by the
integration tests in test_structured_matching_field.py.

Text retrievers add the same column around their paged statement (`Retriever.with_filter_matches`);
its contents for text searches are covered by test_text_and_filter_matching_fields.py.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.core.search.filters.ltree_filters import LtreeFilter
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.core.search.retrieval.retrievers.structured import StructuredRetriever


def _candidate():
    return select(
        AiSearchIndex.entity_id.label("entity_id"), AiSearchIndex.entity_title.label("entity_title")
    ).distinct()


def _compile(filters: FilterTree | None) -> str:
    query = StructuredRetriever(cursor=None, filters=filters).apply(_candidate())
    return str(query.compile(dialect=postgresql.dialect()))


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(FilterOp.HAS_COMPONENT, id="has-component"),
        pytest.param(FilterOp.NOT_HAS_COMPONENT, id="not-has-component"),
    ],
)
def test_component_existence_leaf_produces_no_highlight_column(op: FilterOp) -> None:
    filters = FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(path="*", condition=LtreeFilter(op=op, value="port"), value_kind=UIType.COMPONENT)  # type: ignore[arg-type]
        ],
    )
    sql = _compile(filters)
    assert Retriever.HIGHLIGHT_MATCHES_LABEL not in sql


def test_no_filters_produces_no_highlight_column() -> None:
    sql = _compile(None)
    assert Retriever.HIGHLIGHT_MATCHES_LABEL not in sql


def _tree(leaf: PathFilter) -> FilterTree:
    return FilterTree(op=BooleanOperator.AND, children=[leaf])


_EQ_LEAF = PathFilter(
    path="subscription.status", condition=EqualityFilter(op=FilterOp.EQ, value="active"), value_kind=UIType.STRING
)
_HAS_COMPONENT_LEAF = PathFilter(
    path="*", condition=LtreeFilter(op=FilterOp.HAS_COMPONENT, value="port"), value_kind=UIType.COMPONENT
)


def test_text_retriever_adds_filter_matches_around_the_page() -> None:
    """The column is added outside the paged statement, which is re-ordered by score and id.

    `with_filter_matches` is shared by every text retriever; the integration tests run it for each of them.
    """
    retriever = FuzzyRetriever("fiber", cursor=None)
    page = retriever.apply(_candidate()).limit(10)

    stmt = retriever.with_filter_matches(page, _tree(_EQ_LEAF))

    assert Retriever.HIGHLIGHT_MATCHES_LABEL in stmt.selected_columns
    assert [c.name for c in list(stmt.selected_columns)[:-1]] == [c.name for c in page.selected_columns]
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert sql.rstrip().endswith("ORDER BY page.score DESC NULLS LAST, page.entity_id ASC")


@pytest.mark.parametrize(
    "filters",
    [pytest.param(None, id="no-filters"), pytest.param(_tree(_HAS_COMPONENT_LEAF), id="has-component-only")],
)
def test_text_retriever_without_highlightable_leaves_keeps_page(filters) -> None:
    retriever = FuzzyRetriever("fiber", cursor=None)
    page = retriever.apply(_candidate()).limit(10)

    assert retriever.with_filter_matches(page, filters) is page


def test_structured_retriever_keeps_page_it_already_highlights() -> None:
    """StructuredRetriever selects the column in `apply`, so the page is returned as is."""
    retriever = StructuredRetriever(cursor=None, filters=_tree(_EQ_LEAF))
    page = retriever.apply(_candidate()).limit(10)

    assert retriever.with_filter_matches(page, _tree(_EQ_LEAF)) is page
    assert Retriever.HIGHLIGHT_MATCHES_LABEL in page.selected_columns

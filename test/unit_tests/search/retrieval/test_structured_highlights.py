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
"""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.core.search.filters import FilterTree, PathFilter
from orchestrator.core.search.filters.ltree_filters import LtreeFilter
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.retrievers.structured import StructuredRetriever


def _compile(filters: FilterTree | None) -> str:
    candidate = select(
        AiSearchIndex.entity_id.label("entity_id"), AiSearchIndex.entity_title.label("entity_title")
    ).distinct()
    query = StructuredRetriever(cursor=None, filters=filters).apply(candidate)
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

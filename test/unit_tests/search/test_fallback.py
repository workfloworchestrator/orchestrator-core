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

"""Unit tests for the empty-result broadening waterfall (``execute_search_with_fallback``)."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from orchestrator.core.search.core.types import EntityType, FilterOp, RetrieverType, SearchMetadata, UIType
from orchestrator.core.search.fallback import execute_search_with_fallback
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter, StringFilter
from orchestrator.core.search.query.results import SearchResponse, SearchResult

_EMBEDDING = [0.1, 0.2]
_STATUS = PathFilter(
    path="product.status", condition=EqualityFilter(op=FilterOp.EQ, value="active"), value_kind=UIType.STRING
)
_NAME = PathFilter(
    path="product.name", condition=StringFilter(op=FilterOp.LIKE, value="%node%"), value_kind=UIType.STRING
)
_FILTERS = FilterTree(children=[_STATUS, _NAME])  # one high-signal leaf, one loose leaf
_HIGH_SIGNAL_ONLY = FilterTree(children=[_STATUS])


def _resp(n: int, search_type: str = "fuzzy", embedding: list[float] | None = None) -> SearchResponse:
    results = [
        SearchResult(entity_id=str(i), entity_type=EntityType.PRODUCT, entity_title=f"e{i}", score=1.0)
        for i in range(n)
    ]
    return SearchResponse(
        results=results, metadata=SearchMetadata(search_type=search_type, description=""), query_embedding=embedding
    )


_BASE = {
    "entity_type": EntityType.PRODUCT,
    "filters": _FILTERS,
    "limit": 5,
    "retriever": None,
    "allow_fallback": True,
    "db_session": Mock(),
}


def _patch(*responses):
    return patch("orchestrator.core.search.fallback.engine.execute_search", new=AsyncMock(side_effect=list(responses)))


async def test_structured_results_skip_fallback():
    with _patch(_resp(3)) as m:
        resp, _query, fb = await execute_search_with_fallback(query_text="node", **_BASE)
    assert fb is False
    assert len(resp.results) == 3
    assert m.await_count == 1  # only the structured pass


async def test_empty_broadens_and_flags_fallback():
    with _patch(_resp(0), _resp(2, "semantic")) as m:
        resp, query, fb = await execute_search_with_fallback(query_text="node", **_BASE)
    assert fb is True
    assert len(resp.results) == 2
    assert query.filters == _HIGH_SIGNAL_ONLY  # the broadened pass drops the loose filter
    assert m.await_count == 2  # structured + 1 fallback pass


async def test_fallback_disabled_does_not_broaden():
    with _patch(_resp(0)) as m:
        resp, _query, fb = await execute_search_with_fallback(query_text="node", **{**_BASE, "allow_fallback": False})
    assert fb is False
    assert len(resp.results) == 0
    assert m.await_count == 1  # no fallback passes


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"query_text": None}, id="no_query_text"),  # nothing to rank on without free text
        pytest.param({"query_text": "node", "filters": None}, id="no_filters"),  # nothing to loosen without filters
    ],
)
async def test_without_text_or_filters_does_not_broaden(overrides: dict):
    with _patch(_resp(0)) as m:
        _resp_out, _query, fb = await execute_search_with_fallback(**{**_BASE, **overrides})
    assert fb is False
    assert m.await_count == 1


async def test_broadening_runs_up_to_two_passes():
    # structured empty, first fallback (loose filter dropped) empty, second (no filters) returns rows.
    with _patch(_resp(0, embedding=_EMBEDDING), _resp(0), _resp(4)) as m:
        resp, _query, fb = await execute_search_with_fallback(
            query_text="node", **{**_BASE, "retriever": RetrieverType.FUZZY}
        )
    assert fb is True
    assert len(resp.results) == 4
    assert m.await_count == 3  # structured + 2 fallback passes
    fallback_passes = m.await_args_list[1:]
    assert [call.args[0].filters for call in fallback_passes] == [_HIGH_SIGNAL_ONLY, None]
    # A fallback pass changes the filters only: same retriever, and the query text is not embedded again.
    assert all(call.args[0].retriever == RetrieverType.FUZZY for call in fallback_passes)
    assert all(call.kwargs["query_embedding"] == _EMBEDDING for call in fallback_passes)

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

from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.fallback import SearchEffort, execute_search_with_fallback
from orchestrator.core.search.query.results import SearchResponse, SearchResult


def _resp(n: int, search_type: str = "fuzzy") -> SearchResponse:
    results = [
        SearchResult(entity_id=str(i), entity_type=EntityType.PRODUCT, entity_title=f"e{i}", score=1.0)
        for i in range(n)
    ]
    return SearchResponse(results=results, metadata=SearchMetadata(search_type=search_type, description=""))


_BASE = {"entity_type": EntityType.PRODUCT, "filters": None, "limit": 5, "retriever": None, "db_session": Mock()}


def _patch(*responses):
    return patch("orchestrator.core.search.fallback.engine.execute_search", new=AsyncMock(side_effect=list(responses)))


async def test_structured_results_skip_fallback():
    with _patch(_resp(3)) as m:
        resp, _query, fb = await execute_search_with_fallback(query_text="node", effort=SearchEffort.HIGH, **_BASE)
    assert fb is False
    assert len(resp.results) == 3
    assert m.await_count == 1  # only the structured pass


async def test_empty_broadens_and_flags_fallback():
    with _patch(_resp(0), _resp(2, "semantic")) as m:
        resp, query, fb = await execute_search_with_fallback(query_text="node", effort=SearchEffort.MEDIUM, **_BASE)
    assert fb is True
    assert len(resp.results) == 2
    assert query.filters is None  # the broadened pass drops filters
    assert m.await_count == 2  # structured + 1 fallback pass (MEDIUM)


async def test_low_effort_does_not_broaden():
    with _patch(_resp(0)) as m:
        resp, _query, fb = await execute_search_with_fallback(query_text="node", effort=SearchEffort.LOW, **_BASE)
    assert fb is False
    assert len(resp.results) == 0
    assert m.await_count == 1  # LOW = 0 fallback passes


async def test_no_query_text_does_not_broaden():
    with _patch(_resp(0)) as m:
        _resp_out, _query, fb = await execute_search_with_fallback(query_text=None, effort=SearchEffort.HIGH, **_BASE)
    assert fb is False
    assert m.await_count == 1  # nothing to rank on without free text


async def test_high_effort_runs_up_to_two_passes():
    # structured empty, first fallback (SEMANTIC) empty, second (auto) returns rows.
    with _patch(_resp(0), _resp(0), _resp(4)) as m:
        resp, _query, fb = await execute_search_with_fallback(query_text="node", effort=SearchEffort.HIGH, **_BASE)
    assert fb is True
    assert len(resp.results) == 4
    assert m.await_count == 3  # structured + 2 fallback passes (HIGH)

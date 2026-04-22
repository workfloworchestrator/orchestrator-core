"""Tests for orchestrator.core.search.query.engine -- retriever override selection, search pagination, export, and aggregation."""

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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.core.search.core.types import EntityType, RetrieverType, SearchMetadata
from orchestrator.core.search.query.engine import (
    _get_retriever_from_override,
    execute_aggregation,
    execute_export,
    execute_search,
)
from orchestrator.core.search.query.queries import CountQuery, ExportQuery, SelectQuery
from orchestrator.core.search.query.results import SearchResponse, SearchResult
from orchestrator.core.search.retrieval.retrievers import (
    FuzzyRetriever,
    ProcessHybridRetriever,
    RrfHybridRetriever,
    SemanticRetriever,
)

pytestmark = pytest.mark.search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query(retriever: RetrieverType | None, query_text: str | None, entity_type: EntityType) -> MagicMock:
    q = MagicMock()
    q.retriever = retriever
    q.query_text = query_text
    q.entity_type = entity_type
    return q


def _make_result(entity_id: str) -> SearchResult:
    return SearchResult(
        entity_id=entity_id,
        entity_type=EntityType.SUBSCRIPTION,
        entity_title="Test",
        score=1.0,
    )


def _empty_search_response() -> SearchResponse:
    return SearchResponse(results=[], metadata=SearchMetadata.empty())


# ---------------------------------------------------------------------------
# Tests: _get_retriever_from_override
# ---------------------------------------------------------------------------


def test_get_retriever_no_override_returns_none():
    """query.retriever is None -> returns None."""
    q = _make_query(None, "hello", EntityType.SUBSCRIPTION)
    assert _get_retriever_from_override(q, None, None) is None


@pytest.mark.parametrize(
    "entity_type,expected_type",
    [
        pytest.param(EntityType.SUBSCRIPTION, FuzzyRetriever, id="subscription-fuzzy"),
        pytest.param(EntityType.PRODUCT, FuzzyRetriever, id="product-fuzzy"),
        pytest.param(EntityType.WORKFLOW, FuzzyRetriever, id="workflow-fuzzy"),
        pytest.param(EntityType.PROCESS, ProcessHybridRetriever, id="process-fuzzy"),
    ],
)
def test_get_retriever_fuzzy_override(entity_type: EntityType, expected_type: type):
    """FUZZY override selects FuzzyRetriever or ProcessHybridRetriever for PROCESS."""
    q = _make_query(RetrieverType.FUZZY, "hello", entity_type)
    result = _get_retriever_from_override(q, None, None)
    assert isinstance(result, expected_type)


def test_get_retriever_semantic_override_with_embedding():
    """SEMANTIC override with embedding -> SemanticRetriever."""
    q = _make_query(RetrieverType.SEMANTIC, "hello", EntityType.SUBSCRIPTION)
    embedding = [0.1, 0.2, 0.3]
    result = _get_retriever_from_override(q, None, embedding)
    assert isinstance(result, SemanticRetriever)


def test_get_retriever_semantic_override_without_embedding_raises():
    """SEMANTIC override without embedding -> ValueError."""
    q = _make_query(RetrieverType.SEMANTIC, "hello", EntityType.SUBSCRIPTION)
    with pytest.raises(ValueError, match="Semantic retriever requested but query embedding is not available"):
        _get_retriever_from_override(q, None, None)


@pytest.mark.parametrize(
    "entity_type,expected_type",
    [
        pytest.param(EntityType.SUBSCRIPTION, RrfHybridRetriever, id="subscription-hybrid"),
        pytest.param(EntityType.PRODUCT, RrfHybridRetriever, id="product-hybrid"),
        pytest.param(EntityType.PROCESS, ProcessHybridRetriever, id="process-hybrid"),
    ],
)
def test_get_retriever_hybrid_override_with_embedding(entity_type: EntityType, expected_type: type):
    """HYBRID override with embedding selects RrfHybridRetriever or ProcessHybridRetriever."""
    q = _make_query(RetrieverType.HYBRID, "hello", entity_type)
    embedding = [0.1, 0.2, 0.3]
    result = _get_retriever_from_override(q, None, embedding)
    assert isinstance(result, expected_type)


def test_get_retriever_hybrid_override_without_embedding_raises():
    """HYBRID override without embedding -> ValueError."""
    q = _make_query(RetrieverType.HYBRID, "hello", EntityType.SUBSCRIPTION)
    with pytest.raises(ValueError, match="Hybrid retriever requested but query embedding is not available"):
        _get_retriever_from_override(q, None, None)


@pytest.mark.parametrize(
    "retriever_type",
    [
        pytest.param(RetrieverType.FUZZY, id="fuzzy-no-text"),
        pytest.param(RetrieverType.SEMANTIC, id="semantic-no-text"),
        pytest.param(RetrieverType.HYBRID, id="hybrid-no-text"),
    ],
)
def test_get_retriever_any_override_without_query_text_raises(retriever_type: RetrieverType):
    """Any override without query_text -> ValueError."""
    q = _make_query(retriever_type, None, EntityType.SUBSCRIPTION)
    with pytest.raises(ValueError, match="retriever requested but no query text provided"):
        _get_retriever_from_override(q, None, [0.1, 0.2])


@pytest.mark.parametrize(
    "retriever_type",
    [
        pytest.param(RetrieverType.FUZZY, id="fuzzy-empty-text"),
        pytest.param(RetrieverType.SEMANTIC, id="semantic-empty-text"),
        pytest.param(RetrieverType.HYBRID, id="hybrid-empty-text"),
    ],
)
def test_get_retriever_any_override_with_empty_query_text_raises(retriever_type: RetrieverType):
    """Any override with empty string query_text -> ValueError."""
    q = _make_query(retriever_type, "", EntityType.SUBSCRIPTION)
    with pytest.raises(ValueError, match="retriever requested but no query text provided"):
        _get_retriever_from_override(q, None, [0.1, 0.2])


# ---------------------------------------------------------------------------
# Tests: execute_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_results,expected_has_more,expected_count",
    [
        pytest.param(11, True, 10, id="extra-result-has-more"),
        pytest.param(5, False, 5, id="fewer-results-no-more"),
        pytest.param(10, False, 10, id="exact-limit-no-more"),
        pytest.param(1, False, 1, id="single-result-limit-1"),
    ],
)
async def test_execute_search_pagination(num_results: int, expected_has_more: bool, expected_count: int):
    """Pagination trimming: has_more is True only when results exceed limit."""
    limit = 10 if num_results != 1 else 1
    results = [_make_result(str(i)) for i in range(num_results)]
    mock_response = SearchResponse(results=results, metadata=SearchMetadata.empty())
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=limit)

    with patch("orchestrator.core.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)):
        response = await execute_search(query, db_session=MagicMock())

    assert response.has_more is expected_has_more
    assert len(response.results) == expected_count


# ---------------------------------------------------------------------------
# Tests: execute_export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_export_entity_ids_passed_to_fetch_export_data():
    """entity_ids extracted from search results are forwarded to fetch_export_data."""
    entity_ids = ["aaa", "bbb", "ccc"]
    mock_results = [_make_result(eid) for eid in entity_ids]
    mock_response = SearchResponse(results=mock_results, metadata=SearchMetadata.empty())
    expected_export = [{"id": eid} for eid in entity_ids]

    query = ExportQuery(entity_type=EntityType.SUBSCRIPTION)

    with (
        patch("orchestrator.core.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)),
        patch("orchestrator.core.search.query.engine.fetch_export_data", return_value=expected_export) as mock_fetch,
    ):
        result = await execute_export(query, db_session=MagicMock())

    mock_fetch.assert_called_once_with(EntityType.SUBSCRIPTION, entity_ids)
    assert result == expected_export


@pytest.mark.asyncio
async def test_execute_export_empty_results_returns_empty_list():
    """No search results -> empty export list."""
    mock_response = SearchResponse(results=[], metadata=SearchMetadata.empty())
    query = ExportQuery(entity_type=EntityType.SUBSCRIPTION)

    with (
        patch("orchestrator.core.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)),
        patch("orchestrator.core.search.query.engine.fetch_export_data", return_value=[]) as mock_fetch,
    ):
        result = await execute_export(query, db_session=MagicMock())

    mock_fetch.assert_called_once_with(EntityType.SUBSCRIPTION, [])
    assert result == []


# ---------------------------------------------------------------------------
# Tests: execute_aggregation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_aggregation_simple_count_uses_build_simple_count_query():
    """Simple CountQuery (no group_by, no temporal_group_by) uses build_simple_count_query path."""
    query = CountQuery(entity_type=EntityType.SUBSCRIPTION)

    mock_candidate = MagicMock()
    mock_agg_query = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.mappings.return_value.all.return_value = []

    mock_db = MagicMock()
    mock_db.execute.return_value = mock_mappings

    with (
        patch("orchestrator.core.search.query.engine.build_candidate_query", return_value=mock_candidate),
        patch(
            "orchestrator.core.search.query.engine.build_simple_count_query", return_value=mock_agg_query
        ) as mock_simple,
        patch("orchestrator.core.search.query.engine.build_aggregation_query") as mock_grouped,
        patch("orchestrator.core.search.query.engine.format_aggregation_response") as mock_format,
    ):
        mock_format.return_value = MagicMock()
        await execute_aggregation(query, mock_db)

    mock_simple.assert_called_once_with(mock_candidate)
    mock_grouped.assert_not_called()


@pytest.mark.asyncio
async def test_execute_aggregation_grouped_count_uses_build_aggregation_query():
    """CountQuery with group_by uses build_aggregation_query path."""
    query = CountQuery(entity_type=EntityType.SUBSCRIPTION, group_by=["subscription.status"])

    mock_candidate = MagicMock()
    mock_agg_query = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.mappings.return_value.all.return_value = []

    mock_db = MagicMock()
    mock_db.execute.return_value = mock_mappings

    with (
        patch("orchestrator.core.search.query.engine.build_candidate_query", return_value=mock_candidate),
        patch("orchestrator.core.search.query.engine.build_simple_count_query") as mock_simple,
        patch(
            "orchestrator.core.search.query.engine.build_aggregation_query",
            return_value=(mock_agg_query, ["subscription_status"]),
        ) as mock_grouped,
        patch("orchestrator.core.search.query.engine.format_aggregation_response") as mock_format,
    ):
        mock_format.return_value = MagicMock()
        await execute_aggregation(query, mock_db)

    mock_grouped.assert_called_once_with(query, mock_candidate)
    mock_simple.assert_not_called()


@pytest.mark.asyncio
async def test_execute_aggregation_format_response_called_with_correct_args():
    """format_aggregation_response receives the db result rows and group column names."""
    query = CountQuery(entity_type=EntityType.SUBSCRIPTION)

    mock_candidate = MagicMock()
    mock_agg_query = MagicMock()
    fake_rows = [{"total_count": 42}]
    mock_mappings = MagicMock()
    mock_mappings.mappings.return_value.all.return_value = fake_rows
    mock_db = MagicMock()
    mock_db.execute.return_value = mock_mappings

    with (
        patch("orchestrator.core.search.query.engine.build_candidate_query", return_value=mock_candidate),
        patch("orchestrator.core.search.query.engine.build_simple_count_query", return_value=mock_agg_query),
        patch("orchestrator.core.search.query.engine.format_aggregation_response") as mock_format,
    ):
        mock_format.return_value = MagicMock()
        await execute_aggregation(query, mock_db)

    mock_format.assert_called_once_with(fake_rows, [], query)

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

from orchestrator.search.core.types import EntityType, RetrieverType, SearchMetadata
from orchestrator.search.query.engine import (
    _get_retriever_from_override,
    execute_aggregation,
    execute_export,
    execute_search,
)
from orchestrator.search.query.queries import CountQuery, SelectQuery
from orchestrator.search.query.results import SearchResponse, SearchResult
from orchestrator.search.retrieval.retrievers import (
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


class TestGetRetrieverFromOverride:
    """Unit tests for _get_retriever_from_override."""

    def test_no_override_returns_none(self):
        """query.retriever is None → returns None."""
        q = _make_query(None, "hello", EntityType.SUBSCRIPTION)
        assert _get_retriever_from_override(q, None, None) is None

    @pytest.mark.parametrize(
        "entity_type,expected_type",
        [
            (EntityType.SUBSCRIPTION, FuzzyRetriever),
            (EntityType.PRODUCT, FuzzyRetriever),
            (EntityType.WORKFLOW, FuzzyRetriever),
            (EntityType.PROCESS, ProcessHybridRetriever),
        ],
        ids=["subscription-fuzzy", "product-fuzzy", "workflow-fuzzy", "process-fuzzy"],
    )
    def test_fuzzy_override(self, entity_type: EntityType, expected_type: type):
        """FUZZY override selects FuzzyRetriever or ProcessHybridRetriever for PROCESS."""
        q = _make_query(RetrieverType.FUZZY, "hello", entity_type)
        result = _get_retriever_from_override(q, None, None)
        assert isinstance(result, expected_type)

    def test_semantic_override_with_embedding(self):
        """SEMANTIC override with embedding → SemanticRetriever."""
        q = _make_query(RetrieverType.SEMANTIC, "hello", EntityType.SUBSCRIPTION)
        embedding = [0.1, 0.2, 0.3]
        result = _get_retriever_from_override(q, None, embedding)
        assert isinstance(result, SemanticRetriever)

    def test_semantic_override_without_embedding_raises(self):
        """SEMANTIC override without embedding → ValueError."""
        q = _make_query(RetrieverType.SEMANTIC, "hello", EntityType.SUBSCRIPTION)
        with pytest.raises(ValueError, match="Semantic retriever requested but query embedding is not available"):
            _get_retriever_from_override(q, None, None)

    @pytest.mark.parametrize(
        "entity_type,expected_type",
        [
            (EntityType.SUBSCRIPTION, RrfHybridRetriever),
            (EntityType.PRODUCT, RrfHybridRetriever),
            (EntityType.PROCESS, ProcessHybridRetriever),
        ],
        ids=["subscription-hybrid", "product-hybrid", "process-hybrid"],
    )
    def test_hybrid_override_with_embedding(self, entity_type: EntityType, expected_type: type):
        """HYBRID override with embedding selects RrfHybridRetriever or ProcessHybridRetriever."""
        q = _make_query(RetrieverType.HYBRID, "hello", entity_type)
        embedding = [0.1, 0.2, 0.3]
        result = _get_retriever_from_override(q, None, embedding)
        assert isinstance(result, expected_type)

    def test_hybrid_override_without_embedding_raises(self):
        """HYBRID override without embedding → ValueError."""
        q = _make_query(RetrieverType.HYBRID, "hello", EntityType.SUBSCRIPTION)
        with pytest.raises(ValueError, match="Hybrid retriever requested but query embedding is not available"):
            _get_retriever_from_override(q, None, None)

    @pytest.mark.parametrize(
        "retriever_type",
        [RetrieverType.FUZZY, RetrieverType.SEMANTIC, RetrieverType.HYBRID],
        ids=["fuzzy-no-text", "semantic-no-text", "hybrid-no-text"],
    )
    def test_any_override_without_query_text_raises(self, retriever_type: RetrieverType):
        """Any override without query_text → ValueError."""
        q = _make_query(retriever_type, None, EntityType.SUBSCRIPTION)
        with pytest.raises(ValueError, match="retriever requested but no query text provided"):
            _get_retriever_from_override(q, None, [0.1, 0.2])

    @pytest.mark.parametrize(
        "retriever_type",
        [RetrieverType.FUZZY, RetrieverType.SEMANTIC, RetrieverType.HYBRID],
        ids=["fuzzy-empty-text", "semantic-empty-text", "hybrid-empty-text"],
    )
    def test_any_override_with_empty_query_text_raises(self, retriever_type: RetrieverType):
        """Any override with empty string query_text → ValueError."""
        q = _make_query(retriever_type, "", EntityType.SUBSCRIPTION)
        with pytest.raises(ValueError, match="retriever requested but no query text provided"):
            _get_retriever_from_override(q, None, [0.1, 0.2])


# ---------------------------------------------------------------------------
# Tests: execute_search
# ---------------------------------------------------------------------------


class TestExecuteSearch:
    """Unit tests for execute_search (pagination trimming)."""

    @pytest.mark.asyncio
    async def test_has_more_true_when_extra_result_returned(self):
        """When _execute_search returns limit+1 results, has_more=True and results trimmed."""
        results = [_make_result(str(i)) for i in range(11)]
        mock_response = SearchResponse(results=results, metadata=SearchMetadata.empty())

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10)

        with patch("orchestrator.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)):
            response = await execute_search(query, db_session=MagicMock())

        assert response.has_more is True
        assert len(response.results) == 10

    @pytest.mark.asyncio
    async def test_has_more_false_when_fewer_results(self):
        """When _execute_search returns fewer than limit results, has_more=False."""
        results = [_make_result(str(i)) for i in range(5)]
        mock_response = SearchResponse(results=results, metadata=SearchMetadata.empty())

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10)

        with patch("orchestrator.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)):
            response = await execute_search(query, db_session=MagicMock())

        assert response.has_more is False
        assert len(response.results) == 5

    @pytest.mark.asyncio
    async def test_has_more_false_exact_limit(self):
        """When _execute_search returns exactly limit results, has_more=False."""
        results = [_make_result(str(i)) for i in range(10)]
        mock_response = SearchResponse(results=results, metadata=SearchMetadata.empty())

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10)

        with patch("orchestrator.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)):
            response = await execute_search(query, db_session=MagicMock())

        assert response.has_more is False
        assert len(response.results) == 10

    @pytest.mark.asyncio
    async def test_minimum_limit_single_result_no_more(self):
        """limit=1 with exactly 1 result returned → has_more=False."""
        results = [_make_result("abc")]
        mock_response = SearchResponse(results=results, metadata=SearchMetadata.empty())

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=1)

        with patch("orchestrator.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)):
            response = await execute_search(query, db_session=MagicMock())

        assert response.has_more is False
        assert len(response.results) == 1


# ---------------------------------------------------------------------------
# Tests: execute_export
# ---------------------------------------------------------------------------


class TestExecuteExport:
    """Unit tests for execute_export."""

    @pytest.mark.asyncio
    async def test_entity_ids_passed_to_fetch_export_data(self):
        """entity_ids extracted from search results are forwarded to fetch_export_data."""
        from orchestrator.search.query.queries import ExportQuery

        entity_ids = ["aaa", "bbb", "ccc"]
        mock_results = [_make_result(eid) for eid in entity_ids]
        mock_response = SearchResponse(results=mock_results, metadata=SearchMetadata.empty())
        expected_export = [{"id": eid} for eid in entity_ids]

        query = ExportQuery(entity_type=EntityType.SUBSCRIPTION)

        with (
            patch("orchestrator.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)),
            patch("orchestrator.search.query.engine.fetch_export_data", return_value=expected_export) as mock_fetch,
        ):
            result = await execute_export(query, db_session=MagicMock())

        mock_fetch.assert_called_once_with(EntityType.SUBSCRIPTION, entity_ids)
        assert result == expected_export

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self):
        """No search results → empty export list."""
        from orchestrator.search.query.queries import ExportQuery

        mock_response = SearchResponse(results=[], metadata=SearchMetadata.empty())
        query = ExportQuery(entity_type=EntityType.SUBSCRIPTION)

        with (
            patch("orchestrator.search.query.engine._execute_search", new=AsyncMock(return_value=mock_response)),
            patch("orchestrator.search.query.engine.fetch_export_data", return_value=[]) as mock_fetch,
        ):
            result = await execute_export(query, db_session=MagicMock())

        mock_fetch.assert_called_once_with(EntityType.SUBSCRIPTION, [])
        assert result == []


# ---------------------------------------------------------------------------
# Tests: execute_aggregation
# ---------------------------------------------------------------------------


class TestExecuteAggregation:
    """Unit tests for execute_aggregation."""

    @pytest.mark.asyncio
    async def test_simple_count_uses_build_simple_count_query(self):
        """Simple CountQuery (no group_by, no temporal_group_by) uses build_simple_count_query path."""
        query = CountQuery(entity_type=EntityType.SUBSCRIPTION)

        mock_candidate = MagicMock()
        mock_agg_query = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.mappings.return_value.all.return_value = []

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_mappings

        with (
            patch("orchestrator.search.query.engine.build_candidate_query", return_value=mock_candidate),
            patch(
                "orchestrator.search.query.engine.build_simple_count_query", return_value=mock_agg_query
            ) as mock_simple,
            patch("orchestrator.search.query.engine.build_aggregation_query") as mock_grouped,
            patch("orchestrator.search.query.engine.format_aggregation_response") as mock_format,
        ):
            mock_format.return_value = MagicMock()
            await execute_aggregation(query, mock_db)

        mock_simple.assert_called_once_with(mock_candidate)
        mock_grouped.assert_not_called()

    @pytest.mark.asyncio
    async def test_grouped_count_uses_build_aggregation_query(self):
        """CountQuery with group_by uses build_aggregation_query path."""
        query = CountQuery(entity_type=EntityType.SUBSCRIPTION, group_by=["subscription.status"])

        mock_candidate = MagicMock()
        mock_agg_query = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.mappings.return_value.all.return_value = []

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_mappings

        with (
            patch("orchestrator.search.query.engine.build_candidate_query", return_value=mock_candidate),
            patch("orchestrator.search.query.engine.build_simple_count_query") as mock_simple,
            patch(
                "orchestrator.search.query.engine.build_aggregation_query",
                return_value=(mock_agg_query, ["subscription_status"]),
            ) as mock_grouped,
            patch("orchestrator.search.query.engine.format_aggregation_response") as mock_format,
        ):
            mock_format.return_value = MagicMock()
            await execute_aggregation(query, mock_db)

        mock_grouped.assert_called_once_with(query, mock_candidate)
        mock_simple.assert_not_called()

    @pytest.mark.asyncio
    async def test_format_aggregation_response_called_with_correct_args(self):
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
            patch("orchestrator.search.query.engine.build_candidate_query", return_value=mock_candidate),
            patch("orchestrator.search.query.engine.build_simple_count_query", return_value=mock_agg_query),
            patch("orchestrator.search.query.engine.format_aggregation_response") as mock_format,
        ):
            mock_format.return_value = MagicMock()
            await execute_aggregation(query, mock_db)

        mock_format.assert_called_once_with(fake_rows, [], query)

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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import DBAPIError

from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.engine import execute_aggregation, execute_export, execute_search
from orchestrator.core.search.query.queries import CountQuery, ExportQuery, SelectQuery
from orchestrator.core.search.query.results import SearchResponse, SearchResult
from orchestrator.core.search.retrieval.retrievers.base import SessionSetting

pytestmark = pytest.mark.search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Session settings
# ---------------------------------------------------------------------------


def _rejecting_session(rejected: set[str]) -> MagicMock:
    """A session whose ``set_config`` fails for the given setting names; ``begin_nested`` is a plain context manager."""
    session = MagicMock()
    session.begin_nested.return_value.__enter__ = MagicMock()
    session.begin_nested.return_value.__exit__ = MagicMock(return_value=False)

    def execute(stmt):
        name = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        if any(f"'{r}'" in name for r in rejected):
            raise DBAPIError("set_config", {}, Exception("invalid configuration parameter name"))
        return MagicMock()

    session.execute.side_effect = execute
    return session


def test_apply_session_settings_runs_each_setting_in_a_savepoint():
    session = _rejecting_session(set())
    engine._apply_session_settings(
        session, (SessionSetting("hnsw.iterative_scan", "relaxed_order"), SessionSetting("work_mem", "64MB"))
    )
    assert session.begin_nested.call_count == 2
    assert session.execute.call_count == 2


def test_apply_session_settings_skips_rejected_setting_and_keeps_going():
    session = _rejecting_session({"hnsw.does_not_exist"})
    engine._rejected_session_settings.discard("hnsw.does_not_exist")
    engine._apply_session_settings(
        session, (SessionSetting("hnsw.does_not_exist", "x"), SessionSetting("hnsw.iterative_scan", "relaxed_order"))
    )
    assert session.execute.call_count == 2
    assert "hnsw.does_not_exist" in engine._rejected_session_settings


def test_apply_session_settings_with_nothing_to_apply_touches_no_session():
    session = _rejecting_session(set())
    engine._apply_session_settings(session, ())
    session.execute.assert_not_called()
    session.begin_nested.assert_not_called()

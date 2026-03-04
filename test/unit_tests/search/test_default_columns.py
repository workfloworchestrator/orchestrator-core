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

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.search.aggregations import BaseAggregation
from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, SearchMetadata, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.search.query.default_columns import DEFAULT_RESPONSE_COLUMNS
from orchestrator.search.query.queries import SelectQuery

pytestmark = pytest.mark.search


class TestDefaultResponseColumns:
    """Tests for the DEFAULT_RESPONSE_COLUMNS mapping."""

    def test_all_entity_types_have_defaults(self):
        for entity_type in EntityType:
            assert entity_type in DEFAULT_RESPONSE_COLUMNS, f"Missing defaults for {entity_type}"

    def test_subscription_defaults(self):
        cols = DEFAULT_RESPONSE_COLUMNS[EntityType.SUBSCRIPTION]
        assert all(c.startswith("subscription.") for c in cols)
        assert "subscription.status" in cols
        assert "subscription.product.name" in cols

    def test_process_defaults(self):
        cols = DEFAULT_RESPONSE_COLUMNS[EntityType.PROCESS]
        assert all(c.startswith("process.") for c in cols)
        assert "process.workflow_name" in cols
        assert "process.last_status" in cols

    def test_workflow_defaults(self):
        cols = DEFAULT_RESPONSE_COLUMNS[EntityType.WORKFLOW]
        assert all(c.startswith("workflow.") for c in cols)
        assert "workflow.name" in cols

    def test_product_defaults(self):
        cols = DEFAULT_RESPONSE_COLUMNS[EntityType.PRODUCT]
        assert all(c.startswith("product.") for c in cols)
        assert "product.name" in cols


class TestIncludeColumnsToggle:
    """Tests for the include_columns query parameter on search endpoints."""

    def test_include_columns_false_clears_response_columns(self):
        """When include_columns=False, the query's response_columns should be set to empty list."""
        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10)
        assert query.response_columns is None

        updated = query.model_copy(update={"response_columns": []})
        assert updated.response_columns == []

    def test_include_columns_true_preserves_response_columns(self):
        """When include_columns=True (default), response_columns should be untouched."""
        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10, response_columns=["subscription.status"])
        assert query.response_columns == ["subscription.status"]


def _make_search_row(entity_id: str, entity_title: str, score: float = 0.92) -> MagicMock:
    """Create a mock DB row matching what the search retriever returns."""
    row = MagicMock()
    row.entity_id = entity_id
    row.entity_title = entity_title
    row.score = score
    row.get = lambda key, default=None: {"entity_title": entity_title, "perfect_match": 0}.get(key, default)
    return row


def _make_column_row(entity_id: str, columns: dict[str, str | None]) -> SimpleNamespace:
    """Create a fake DB row matching what the column pivot query returns.

    Converts field paths to aliases (e.g. 'subscription.status' -> 'subscription_status')
    just like the real SQL query does via BaseAggregation.field_to_alias.
    """
    attrs = {"entity_id": entity_id}
    for path, value in columns.items():
        alias = BaseAggregation.field_to_alias(path)
        attrs[alias] = value
    return SimpleNamespace(**attrs)


SIMPLE_FILTER = FilterTree(
    op=BooleanOperator.AND,
    children=[
        PathFilter(
            path="subscription.status",
            condition=EqualityFilter(op=FilterOp.EQ, value="active"),
            value_kind=UIType.STRING,
        ),
    ],
)


class TestResponseColumns:
    """Tests verifying column data flows through to SearchResult.response_columns.

    Only the DB session and retriever are mocked (infrastructure).
    The real business logic runs: process_response_columns, format_search_response,
    and the default column resolution in the engine.

    Mirrors the 3 API scenarios:
    1. No response_columns → returns default columns for entity type
    2. Custom response_columns → returns only those columns
    3. include_columns=false (empty list) → null response_columns
    """

    @pytest.fixture
    def mock_db_session(self):
        return MagicMock()

    @pytest.fixture
    def mock_retriever(self):
        retriever = MagicMock()
        retriever.metadata = SearchMetadata(search_type="structured", description="test")
        retriever.apply.side_effect = lambda stmt: stmt
        return retriever

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.engine.build_candidate_query")
    @patch("orchestrator.search.query.engine.Retriever")
    async def test_no_response_columns_returns_defaults(
        self,
        mock_retriever_cls,
        _mock_build_candidate,
        mock_db_session,
        mock_retriever,
    ):
        """Scenario 1: No response_columns → default columns appear on SearchResult."""
        from orchestrator.search.query.engine import _execute_search

        mock_retriever_cls.route.return_value = mock_retriever

        search_row = _make_search_row("id-1", "my-service")
        default_cols = DEFAULT_RESPONSE_COLUMNS[EntityType.SUBSCRIPTION]
        col_values = {col: f"value-{i}" for i, col in enumerate(default_cols)}
        column_row = _make_column_row("id-1", col_values)

        mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]
        mock_db_session.execute.return_value.all.return_value = [column_row]

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10, filters=SIMPLE_FILTER)

        response = await _execute_search(query, mock_db_session, limit=10)

        result = response.results[0]
        assert result.response_columns is not None
        assert set(result.response_columns.keys()) == set(default_cols)
        for col in default_cols:
            assert result.response_columns[col] == col_values[col]

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.engine.build_candidate_query")
    @patch("orchestrator.search.query.engine.Retriever")
    async def test_custom_response_columns_returns_only_requested(
        self,
        mock_retriever_cls,
        _mock_build_candidate,
        mock_db_session,
        mock_retriever,
    ):
        """Scenario 2: Custom response_columns → only those columns on SearchResult."""
        from orchestrator.search.query.engine import _execute_search

        mock_retriever_cls.route.return_value = mock_retriever

        custom_cols = ["subscription.status", "subscription.product.name"]
        col_values = {"subscription.status": "active", "subscription.product.name": "IP Transit"}

        search_row = _make_search_row("id-1", "my-service")
        column_row = _make_column_row("id-1", col_values)

        mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]
        mock_db_session.execute.return_value.all.return_value = [column_row]

        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION, limit=10, filters=SIMPLE_FILTER, response_columns=custom_cols
        )

        response = await _execute_search(query, mock_db_session, limit=10)

        result = response.results[0]
        assert result.response_columns is not None
        assert set(result.response_columns.keys()) == set(custom_cols)
        assert result.response_columns["subscription.status"] == "active"
        assert result.response_columns["subscription.product.name"] == "IP Transit"
        assert "subscription.description" not in result.response_columns

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.engine.build_candidate_query")
    @patch("orchestrator.search.query.engine.Retriever")
    async def test_empty_response_columns_returns_null(
        self,
        mock_retriever_cls,
        _mock_build_candidate,
        mock_db_session,
        mock_retriever,
    ):
        """Scenario 3: Empty response_columns (include_columns=false) → null on SearchResult."""
        from orchestrator.search.query.engine import _execute_search

        mock_retriever_cls.route.return_value = mock_retriever

        search_row = _make_search_row("id-1", "my-service")
        mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10, filters=SIMPLE_FILTER, response_columns=[])

        response = await _execute_search(query, mock_db_session, limit=10)

        result = response.results[0]
        assert result.response_columns is None

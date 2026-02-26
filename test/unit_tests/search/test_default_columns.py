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

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp
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


class TestEngineDefaultColumns:
    """Tests that the engine applies default columns correctly."""

    @pytest.fixture
    def mock_result_row(self):
        row = MagicMock()
        row.entity_id = "test-id-123"
        return row

    @pytest.fixture
    def simple_filter(self):
        return FilterTree(
            op=BooleanOperator.AND,
            children=[
                PathFilter(
                    path="subscription.status",
                    condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                    value_kind="string",
                ),
            ],
        )

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.engine.build_response_columns_query")
    @patch("orchestrator.search.query.engine.process_response_columns")
    @patch("orchestrator.search.query.engine.build_candidate_query")
    @patch("orchestrator.search.query.engine.Retriever")
    async def test_defaults_applied_when_response_columns_is_none(
        self,
        mock_retriever_cls,
        mock_build_candidate,
        mock_process_cols,
        mock_build_cols,
        mock_result_row,
        simple_filter,
    ):
        """When query.response_columns is None, engine should use defaults."""
        from orchestrator.search.query.engine import _execute_search

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10, filters=simple_filter)
        assert query.response_columns is None

        mock_session = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.metadata = MagicMock()
        mock_retriever_cls.route.return_value = mock_retriever
        mock_retriever.apply.return_value = MagicMock()

        mock_session.execute.return_value.mappings.return_value.all.return_value = [mock_result_row]
        mock_process_cols.return_value = {"test-id-123": {"subscription.status": "active"}}

        with patch("orchestrator.search.query.engine.format_search_response") as mock_format:
            mock_format.return_value = MagicMock()
            await _execute_search(query, mock_session, limit=10)

        expected_cols = DEFAULT_RESPONSE_COLUMNS[EntityType.SUBSCRIPTION]
        mock_build_cols.assert_called_once()
        actual_cols = mock_build_cols.call_args[0][2]
        assert actual_cols == expected_cols

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.engine.build_response_columns_query")
    @patch("orchestrator.search.query.engine.process_response_columns")
    @patch("orchestrator.search.query.engine.build_candidate_query")
    @patch("orchestrator.search.query.engine.Retriever")
    async def test_explicit_response_columns_override_defaults(
        self,
        mock_retriever_cls,
        mock_build_candidate,
        mock_process_cols,
        mock_build_cols,
        mock_result_row,
        simple_filter,
    ):
        """When query.response_columns is set, engine should use those instead of defaults."""
        from orchestrator.search.query.engine import _execute_search

        explicit_cols = ["subscription.status"]
        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION, limit=10, filters=simple_filter, response_columns=explicit_cols
        )

        mock_session = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.metadata = MagicMock()
        mock_retriever_cls.route.return_value = mock_retriever
        mock_retriever.apply.return_value = MagicMock()

        mock_session.execute.return_value.mappings.return_value.all.return_value = [mock_result_row]
        mock_process_cols.return_value = {"test-id-123": {"subscription.status": "active"}}

        with patch("orchestrator.search.query.engine.format_search_response") as mock_format:
            mock_format.return_value = MagicMock()
            await _execute_search(query, mock_session, limit=10)

        mock_build_cols.assert_called_once()
        actual_cols = mock_build_cols.call_args[0][2]
        assert actual_cols == explicit_cols

    @pytest.mark.asyncio
    @patch("orchestrator.search.query.engine.build_response_columns_query")
    @patch("orchestrator.search.query.engine.build_candidate_query")
    @patch("orchestrator.search.query.engine.Retriever")
    async def test_empty_response_columns_skips_column_fetch(
        self,
        mock_retriever_cls,
        mock_build_candidate,
        mock_build_cols,
        mock_result_row,
        simple_filter,
    ):
        """When response_columns is an empty list, column fetching should be skipped."""
        from orchestrator.search.query.engine import _execute_search

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10, filters=simple_filter, response_columns=[])

        mock_session = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.metadata = MagicMock()
        mock_retriever_cls.route.return_value = mock_retriever
        mock_retriever.apply.return_value = MagicMock()

        mock_session.execute.return_value.mappings.return_value.all.return_value = [mock_result_row]

        with patch("orchestrator.search.query.engine.format_search_response") as mock_format:
            mock_format.return_value = MagicMock()
            await _execute_search(query, mock_session, limit=10)

        mock_build_cols.assert_not_called()


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

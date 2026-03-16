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

from orchestrator.api.api_v1.endpoints.search import _perform_search_and_fetch
from orchestrator.schemas.search_requests import SearchRequest
from orchestrator.search.core.types import EntityType
from orchestrator.search.query.default_columns import DEFAULT_RESPONSE_COLUMNS
from orchestrator.search.query.engine import execute_search
from orchestrator.search.query.queries import SelectQuery

from .fixtures.helpers import SIMPLE_SUBSCRIPTION_FILTER, make_column_row, make_search_row


class TestResponseColumns:
    """Tests for response_columns: defaults, overrides, toggle, and end-to-end data flow.

    Only the DB session is mocked (infrastructure).
    The real business logic runs: process_response_columns, format_search_response,
    and the default column resolution in the engine.
    """

    # --- DEFAULT_RESPONSE_COLUMNS mapping ---

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

    # --- include_columns toggle ---

    @pytest.mark.asyncio
    async def test_include_columns_false_passes_empty_response_columns_to_engine(self):
        """When include_columns=False, _perform_search_and_fetch passes response_columns=[] to the engine."""
        request = SearchRequest(limit=10)
        mock_response = MagicMock(results=[], metadata=MagicMock())

        with (
            patch(
                "orchestrator.api.api_v1.endpoints.search.engine.execute_search", new_callable=AsyncMock
            ) as mock_execute,
            patch("orchestrator.api.api_v1.endpoints.search.db"),
        ):
            mock_execute.return_value = mock_response
            await _perform_search_and_fetch(EntityType.SUBSCRIPTION, request, include_columns=False)

        called_query = mock_execute.call_args[0][0]
        assert called_query.response_columns == []

    @pytest.mark.asyncio
    async def test_include_columns_true_preserves_response_columns_in_engine(self):
        """When include_columns=True (default), _perform_search_and_fetch passes response_columns unchanged."""
        request = SearchRequest(limit=10, response_columns=["subscription.status"])
        mock_response = MagicMock(results=[], metadata=MagicMock())

        with (
            patch(
                "orchestrator.api.api_v1.endpoints.search.engine.execute_search", new_callable=AsyncMock
            ) as mock_execute,
            patch("orchestrator.api.api_v1.endpoints.search.db"),
        ):
            mock_execute.return_value = mock_response
            await _perform_search_and_fetch(EntityType.SUBSCRIPTION, request, include_columns=True)

        called_query = mock_execute.call_args[0][0]
        assert called_query.response_columns == ["subscription.status"]

    # --- End-to-end: 3 API scenarios ---

    @pytest.mark.asyncio
    async def test_no_response_columns_returns_defaults(self, mock_db_session):
        """Scenario 1: No response_columns → default columns appear on SearchResult."""

        search_row = make_search_row("id-1", "my-service")
        default_cols = DEFAULT_RESPONSE_COLUMNS[EntityType.SUBSCRIPTION]
        col_values = {col: f"value-{i}" for i, col in enumerate(default_cols)}
        column_row = make_column_row("id-1", col_values)

        mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]
        mock_db_session.execute.return_value.all.return_value = [column_row]

        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, limit=10, filters=SIMPLE_SUBSCRIPTION_FILTER)

        response = await execute_search(query, mock_db_session)

        result = response.results[0]
        assert result.response_columns is not None
        assert set(result.response_columns.keys()) == set(default_cols)
        for col in default_cols:
            assert result.response_columns[col] == col_values[col]

    @pytest.mark.asyncio
    async def test_custom_response_columns_returns_only_requested(self, mock_db_session):
        """Scenario 2: Custom response_columns → only those columns on SearchResult."""

        custom_cols = ["subscription.status", "subscription.product.name"]
        col_values = {"subscription.status": "active", "subscription.product.name": "IP Transit"}

        search_row = make_search_row("id-1", "my-service")
        column_row = make_column_row("id-1", col_values)

        mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]
        mock_db_session.execute.return_value.all.return_value = [column_row]

        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            limit=10,
            filters=SIMPLE_SUBSCRIPTION_FILTER,
            response_columns=custom_cols,
        )

        response = await execute_search(query, mock_db_session)

        result = response.results[0]
        assert result.response_columns is not None
        assert set(result.response_columns.keys()) == set(custom_cols)

    @pytest.mark.asyncio
    async def test_empty_response_columns_returns_null(self, mock_db_session):
        """Scenario 3: Empty response_columns (include_columns=false) → null on SearchResult."""

        search_row = make_search_row("id-1", "my-service")
        mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]

        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION, limit=10, filters=SIMPLE_SUBSCRIPTION_FILTER, response_columns=[]
        )

        response = await execute_search(query, mock_db_session)

        result = response.results[0]
        assert result.response_columns is None

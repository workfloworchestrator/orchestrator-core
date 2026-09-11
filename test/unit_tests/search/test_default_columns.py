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

"""Tests for response_columns: include_columns toggle and end-to-end data flow through search engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.core.api.api_v1.endpoints.search import _perform_search_and_fetch
from orchestrator.core.schemas.search_requests import SearchRequest
from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.query.engine import execute_search
from orchestrator.core.search.query.queries import SelectQuery
from test.unit_tests.search.fixtures.helpers import (
    SIMPLE_SUBSCRIPTION_FILTER,
    make_column_row,
    make_list_rows,
    make_search_row,
)

# --- include_columns toggle ---


@pytest.mark.parametrize(
    "include_columns,input_cols,expected_cols",
    [
        pytest.param(False, None, [], id="false-passes-empty"),
        pytest.param(True, ["subscription.status"], ["subscription.status"], id="true-preserves"),
    ],
)
@pytest.mark.asyncio
async def test_include_columns_toggle(include_columns, input_cols, expected_cols):
    kwargs = {"limit": 10}
    if input_cols is not None:
        kwargs["response_columns"] = input_cols
    request = SearchRequest(**kwargs)
    mock_response = MagicMock(results=[], metadata=SearchMetadata.empty())

    with patch(
        "orchestrator.core.api.api_v1.endpoints.search.engine.execute_search", new_callable=AsyncMock
    ) as mock_execute:
        mock_execute.return_value = mock_response
        await _perform_search_and_fetch(AsyncMock(), EntityType.SUBSCRIPTION, request, include_columns=include_columns)

    called_query = mock_execute.call_args[0][0]
    assert called_query.response_columns == expected_cols


# --- End-to-end scenarios ---


@pytest.mark.parametrize(
    "response_columns,has_column_rows,expect_response_columns",
    [
        pytest.param(None, False, False, id="no-columns-returns-null"),
        pytest.param([], False, False, id="empty-columns-returns-null"),
    ],
)
@pytest.mark.asyncio
async def test_response_columns_null_scenarios(
    mock_db_session, response_columns, has_column_rows, expect_response_columns
):
    search_row = make_search_row("id-1", "my-service")
    mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]

    query_kwargs = {"entity_type": EntityType.SUBSCRIPTION, "limit": 10, "filters": SIMPLE_SUBSCRIPTION_FILTER}
    if response_columns is not None:
        query_kwargs["response_columns"] = response_columns
    query = SelectQuery(**query_kwargs)

    response = await execute_search(query, mock_db_session)
    assert response.results[0].response_columns is None


@pytest.mark.asyncio
async def test_custom_response_columns_returns_only_requested(mock_db_session):
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
async def test_wildcard_response_columns_returns_grouped_list(mock_db_session):
    """Wildcard response_columns (e.g. process.subscriptions.*.field) are grouped into a list."""
    list_cols = ["process.subscriptions.*.subscription_id", "process.subscriptions.*.description"]
    items = [
        {"subscription_id": "uuid1", "description": "desc1"},
        {"subscription_id": "uuid2", "description": "desc2"},
    ]

    search_row = make_search_row("id-1", "my-process")
    list_rows = make_list_rows("id-1", "process.subscriptions", items)

    mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]
    mock_db_session.execute.return_value.all.return_value = list_rows

    query = SelectQuery(
        entity_type=EntityType.PROCESS,
        limit=10,
        filters=SIMPLE_SUBSCRIPTION_FILTER,
        response_columns=list_cols,
    )

    response = await execute_search(query, mock_db_session)

    result = response.results[0]
    assert result.response_columns == {"process.subscriptions": items}


@pytest.mark.asyncio
async def test_wildcard_response_columns_empty_list_for_entity_without_rows(mock_db_session):
    """An entity with no matching list rows still gets an (empty) list, not a missing key."""
    list_cols = ["process.subscriptions.*.subscription_id"]

    search_row = make_search_row("id-1", "my-process")

    mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]
    mock_db_session.execute.return_value.all.return_value = []

    query = SelectQuery(
        entity_type=EntityType.PROCESS,
        limit=10,
        filters=SIMPLE_SUBSCRIPTION_FILTER,
        response_columns=list_cols,
    )

    response = await execute_search(query, mock_db_session)

    result = response.results[0]
    assert result.response_columns == {"process.subscriptions": []}


@pytest.mark.asyncio
async def test_mixed_flat_and_wildcard_response_columns(mock_db_session):
    """Flat and wildcard response_columns can be requested together and both are populated."""
    mixed_cols = ["process.workflow_name", "process.subscriptions.*.subscription_id"]
    items = [{"subscription_id": "uuid1"}]

    search_row = make_search_row("id-1", "my-process")
    column_row = make_column_row("id-1", {"process.workflow_name": "create_service"})
    list_rows = make_list_rows("id-1", "process.subscriptions", items)

    mock_db_session.execute.return_value.mappings.return_value.all.return_value = [search_row]
    # Both the flat pivot query and the list-rows query go through `.execute(...).all()`;
    # the flat query runs first, so its rows are returned on the first `.execute()` call.
    mock_db_session.execute.side_effect = [
        mock_db_session.execute.return_value,  # initial candidate/search query (uses .mappings())
        MagicMock(all=MagicMock(return_value=[column_row])),
        MagicMock(all=MagicMock(return_value=list_rows)),
    ]

    query = SelectQuery(
        entity_type=EntityType.PROCESS,
        limit=10,
        filters=SIMPLE_SUBSCRIPTION_FILTER,
        response_columns=mixed_cols,
    )

    response = await execute_search(query, mock_db_session)

    result = response.results[0]
    assert result.response_columns == {
        "process.workflow_name": "create_service",
        "process.subscriptions": items,
    }

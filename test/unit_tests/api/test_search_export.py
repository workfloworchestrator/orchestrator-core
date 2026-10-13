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

"""Tests for POST /api/search/{entity}/export: export limit, query passthrough, response shape and errors."""

from http import HTTPStatus
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from orchestrator.core.api.api_v1.endpoints.search import EXPORT_ENTITY_TYPES, SearchExportEntity, router
from orchestrator.core.db import get_async_session
from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.query.queries import BaseQuery, ExportQuery
from orchestrator.core.search.query.results import SearchResponse, SearchResult
from test.unit_tests.search.fixtures.helpers import SIMPLE_SUBSCRIPTION_FILTER

pytestmark = pytest.mark.search

ENGINE_PATH = "orchestrator.core.api.api_v1.endpoints.search.engine.execute_search"
VALIDATE_PATH = "orchestrator.core.api.api_v1.endpoints.search.validate_structured_order_by_element"

FILTERS = SIMPLE_SUBSCRIPTION_FILTER.model_dump(mode="json")


def _result(entity_id: str) -> SearchResult:
    return SearchResult(entity_id=entity_id, entity_type=EntityType.SUBSCRIPTION, entity_title="t", score=1.0)


def _response(count: int, has_more: bool = False, total_items: int | None = None) -> SearchResponse:
    return SearchResponse(
        results=[_result(str(i)) for i in range(count)],
        metadata=SearchMetadata.empty(),
        has_more=has_more,
        total_items=total_items,
        start_cursor=0 if total_items else None,
        end_cursor=count - 1 if total_items else None,
    )


@pytest.fixture
def test_client():
    """Client for the search router only, so the tests don't depend on auth or a database."""

    async def _session() -> AsyncIterator[AsyncSession]:
        yield AsyncMock(spec=AsyncSession)

    app = FastAPI()
    app.include_router(router, prefix="/api/search")
    app.dependency_overrides[get_async_session] = _session
    return TestClient(app)


@pytest.fixture
def mock_execute_search():
    with (
        patch(VALIDATE_PATH, new=AsyncMock()),
        patch(ENGINE_PATH, new_callable=AsyncMock) as mock_execute,
    ):
        mock_execute.return_value = _response(0)
        yield mock_execute


def test_every_export_entity_is_mapped():
    assert set(EXPORT_ENTITY_TYPES) == set(SearchExportEntity)
    assert set(EXPORT_ENTITY_TYPES.values()) == set(EntityType)


@pytest.mark.parametrize("entity,entity_type", list(EXPORT_ENTITY_TYPES.items()))
def test_export_routes_entity_type(test_client, mock_execute_search, entity, entity_type):
    response = test_client.post(f"/api/search/{entity.value}/export", json={"filters": FILTERS})

    assert response.status_code == HTTPStatus.OK
    query = mock_execute_search.call_args[0][0]
    assert isinstance(query, ExportQuery)
    assert query.entity_type == entity_type


@pytest.mark.parametrize(
    "limit",
    [
        pytest.param(BaseQuery.MAX_LIMIT + 1, id="above-search-max"),
        pytest.param(500, id="between-search-and-export-max"),
        pytest.param(BaseQuery.MAX_EXPORT_LIMIT, id="export-max"),
    ],
)
def test_export_accepts_limits_above_search_max(test_client, mock_execute_search, limit):
    response = test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS, "limit": limit})

    assert response.status_code == HTTPStatus.OK
    assert mock_execute_search.call_args[0][0].limit == limit


@pytest.mark.parametrize(
    "limit",
    [
        pytest.param(BaseQuery.MIN_LIMIT - 1, id="below-min"),
        pytest.param(BaseQuery.MAX_EXPORT_LIMIT + 1, id="above-export-max"),
    ],
)
def test_export_rejects_out_of_range_limits(test_client, mock_execute_search, limit):
    response = test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS, "limit": limit})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["detail"][0]["loc"] == ["body", "limit"]
    mock_execute_search.assert_not_called()


def test_search_endpoint_still_capped_at_search_max(test_client, mock_execute_search):
    response = test_client.post("/api/search/subscriptions", json={"filters": FILTERS, "limit": 5768})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["detail"][0]["ctx"] == {"le": BaseQuery.MAX_LIMIT}


def test_export_unknown_entity_returns_422(test_client, mock_execute_search):
    response = test_client.post("/api/search/customers/export", json={"filters": FILTERS})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    mock_execute_search.assert_not_called()


def test_export_passes_order_by_and_response_columns(test_client, mock_execute_search):
    body = {
        "filters": FILTERS,
        "limit": 500,
        "order_by": {"element": "subscription.description", "direction": "desc"},
        "response_columns": ["subscription.status", "subscription.product.name"],
    }
    test_client.post("/api/search/subscriptions/export", json=body)

    query = mock_execute_search.call_args[0][0]
    assert query.order_by.element == "subscription.description"
    assert query.response_columns == ["subscription.status", "subscription.product.name"]


def test_export_without_limit_uses_max_export_limit(test_client, mock_execute_search):
    response = test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS})

    assert response.status_code == HTTPStatus.OK
    assert mock_execute_search.call_args[0][0].limit == BaseQuery.MAX_EXPORT_LIMIT


def test_export_does_not_paginate(test_client, mock_execute_search):
    test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS})

    assert mock_execute_search.call_args[0][2:] == ()
    assert "cursor" not in mock_execute_search.call_args.kwargs


@pytest.mark.parametrize(
    "count,has_more,total_items,expected_cursor",
    [
        pytest.param(3, True, 10, {"total_items": 10, "start_cursor": 0, "end_cursor": 2}, id="truncated-with-total"),
        pytest.param(3, False, 3, {"total_items": 3, "start_cursor": 0, "end_cursor": 2}, id="complete-with-total"),
        pytest.param(3, False, None, None, id="no-total-non-structured"),
        pytest.param(0, False, None, None, id="empty"),
    ],
)
def test_export_response_shape(test_client, mock_execute_search, count, has_more, total_items, expected_cursor):
    mock_execute_search.return_value = _response(count, has_more=has_more, total_items=total_items)

    response = test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS})

    body = response.json()
    assert response.status_code == HTTPStatus.OK
    assert [row["entity_id"] for row in body["data"]] == [str(i) for i in range(count)]
    assert body["page_info"] == {"has_next_page": has_more, "next_page_cursor": None}
    assert body["cursor"] == expected_cursor


@pytest.mark.parametrize(
    "error,expected_status,detail_prefix",
    [
        pytest.param(ValueError("bad path"), HTTPStatus.UNPROCESSABLE_ENTITY, "bad path", id="value-error"),
        pytest.param(RuntimeError("boom"), HTTPStatus.INTERNAL_SERVER_ERROR, "Export failed: boom", id="other-error"),
    ],
)
def test_export_engine_errors(test_client, mock_execute_search, error, expected_status, detail_prefix):
    mock_execute_search.side_effect = error

    response = test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS})

    assert response.status_code == expected_status
    assert response.json()["detail"] == detail_prefix


def test_export_invalid_order_by_returns_422(test_client):
    with (
        patch(VALIDATE_PATH, new=AsyncMock(side_effect=ValueError("Element x is not a valid path"))),
        patch(ENGINE_PATH, new_callable=AsyncMock) as mock_execute,
    ):
        response = test_client.post(
            "/api/search/subscriptions/export", json={"filters": FILTERS, "order_by": {"element": "x"}}
        )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["detail"] == "Element x is not a valid path"
    mock_execute.assert_not_called()

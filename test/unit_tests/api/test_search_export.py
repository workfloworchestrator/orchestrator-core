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
    "body_limit,expected_status,expected_limit",
    [
        pytest.param(None, HTTPStatus.OK, BaseQuery.MAX_EXPORT_LIMIT, id="defaults-to-max"),
        pytest.param(BaseQuery.MAX_LIMIT + 1, HTTPStatus.OK, BaseQuery.MAX_LIMIT + 1, id="above-search-max"),
        pytest.param(BaseQuery.MAX_EXPORT_LIMIT + 1, HTTPStatus.UNPROCESSABLE_ENTITY, None, id="above-export-max"),
    ],
)
def test_export_limit(test_client, mock_execute_search, body_limit, expected_status, expected_limit):
    body = {"filters": FILTERS} | ({"limit": body_limit} if body_limit is not None else {})
    response = test_client.post("/api/search/subscriptions/export", json=body)

    assert response.status_code == expected_status
    if expected_limit is None:
        mock_execute_search.assert_not_called()
    else:
        assert mock_execute_search.call_args[0][0].limit == expected_limit


def test_export_passes_order_by_and_response_columns(test_client, mock_execute_search):
    body = {
        "filters": FILTERS,
        "order_by": {"element": "subscription.description", "direction": "desc"},
        "response_columns": ["subscription.status", "subscription.product.name"],
    }
    test_client.post("/api/search/subscriptions/export", json=body)

    query = mock_execute_search.call_args[0][0]
    assert query.order_by.element == "subscription.description"
    assert query.response_columns == ["subscription.status", "subscription.product.name"]


def test_export_truncated_response(test_client, mock_execute_search):
    mock_execute_search.return_value = _response(3, has_more=True, total_items=10)

    body = test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS}).json()

    assert [row["entity_id"] for row in body["data"]] == ["0", "1", "2"]
    assert body["page_info"] == {"has_next_page": True, "next_page_cursor": None}
    assert body["cursor"]["total_items"] == 10


@pytest.mark.parametrize(
    "patch_path,error,expected_status,expected_detail",
    [
        pytest.param(VALIDATE_PATH, ValueError("bad path"), HTTPStatus.UNPROCESSABLE_ENTITY, "bad path", id="invalid"),
        pytest.param(
            ENGINE_PATH, RuntimeError("boom"), HTTPStatus.INTERNAL_SERVER_ERROR, "Export failed: boom", id="error"
        ),
    ],
)
def test_export_errors(test_client, mock_execute_search, patch_path, error, expected_status, expected_detail):
    with patch(patch_path, new=AsyncMock(side_effect=error)):
        response = test_client.post("/api/search/subscriptions/export", json={"filters": FILTERS})

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail

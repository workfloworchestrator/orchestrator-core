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

"""Tests for rendering an exhausted database connection pool as a 503."""

from http import HTTPStatus
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.testclient import TestClient

from orchestrator.core.exception_handlers import DATABASE_UNAVAILABLE_MESSAGE, database_timeout_handler

POOL_TIMEOUT = SQLAlchemyTimeoutError(
    "QueuePool limit of size 1 overflow 0 reached, connection timed out, timeout 1.00"
)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(SQLAlchemyTimeoutError, database_timeout_handler)  # type: ignore[arg-type]

    @app.get("/api/subscriptions")
    def fail() -> None:
        raise POOL_TIMEOUT

    return TestClient(app)


def test_pool_timeout_returns_503_with_retry_after(client: TestClient) -> None:
    response = client.get("/api/subscriptions")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": DATABASE_UNAVAILABLE_MESSAGE,
        "status": HTTPStatus.SERVICE_UNAVAILABLE.value,
        "title": HTTPStatus.SERVICE_UNAVAILABLE.phrase,
    }
    assert response.headers["Retry-After"] == "5"


def test_pool_timeout_is_logged_as_a_warning(client: TestClient) -> None:
    with patch("orchestrator.core.exception_handlers.logger") as mock_logger:
        client.get("/api/subscriptions")

    mock_logger.warning.assert_called_once()
    assert mock_logger.warning.call_args.args[0] == "Database connection pool exhausted"
    assert mock_logger.warning.call_args.kwargs["path"] == "/api/subscriptions"

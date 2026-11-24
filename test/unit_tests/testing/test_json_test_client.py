# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

"""Tests for ``JsonTestClient`` in orchestrator/core/testing/fixtures.py."""

import json
import warnings
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from orchestrator.core.testing.fixtures import JsonTestClient

UUID_VALUE = UUID("11111111-2222-3333-4444-555555555555")
DATETIME_VALUE = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


async def echo(request: Request) -> JSONResponse:
    body = await request.body()
    return JSONResponse(
        {
            "content_type": request.headers.get("content-type"),
            "x_custom": request.headers.get("x-custom"),
            "body": body.decode(),
        }
    )


@pytest.fixture
def client() -> JsonTestClient:
    return JsonTestClient(Starlette(routes=[Route("/echo", echo, methods=["POST", "PUT"])]))


@pytest.mark.parametrize(
    "json_body,expected",
    [
        pytest.param({"a": 1}, {"a": 1}, id="dict"),
        pytest.param([1, "two"], [1, "two"], id="list"),
        pytest.param({}, {}, id="empty-dict-is-still-sent"),
        pytest.param([], [], id="empty-list-is-still-sent"),
        pytest.param(0, 0, id="falsy-int-is-still-sent"),
        pytest.param(False, False, id="falsy-bool-is-still-sent"),
        pytest.param({"id": UUID_VALUE}, {"id": str(UUID_VALUE)}, id="uuid-uses-orchestrator-encoder"),
        pytest.param(
            {"at": DATETIME_VALUE}, {"at": "2026-01-02T03:04:05+00:00"}, id="datetime-uses-orchestrator-encoder"
        ),
    ],
)
def test_json_is_serialized_with_orchestrator_encoder(client: JsonTestClient, json_body: Any, expected: Any) -> None:
    response = client.request("POST", "/echo", json=json_body)

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] == "application/json"
    assert json.loads(payload["body"]) == expected


@pytest.mark.parametrize("method", ["post", "put"])
def test_verb_helpers_route_json_through_the_encoder(client: JsonTestClient, method: str) -> None:
    response = getattr(client, method)("/echo", json={"id": UUID_VALUE})

    assert json.loads(response.json()["body"]) == {"id": str(UUID_VALUE)}


@pytest.mark.parametrize(
    "headers,expected_x_custom",
    [
        pytest.param(None, None, id="no-headers"),
        pytest.param({"X-Custom": "yes"}, "yes", id="custom-header-kept"),
        pytest.param({"Content-Type": "text/plain", "X-Custom": "yes"}, "yes", id="content-type-overridden"),
    ],
)
def test_json_headers_are_merged(client: JsonTestClient, headers: dict | None, expected_x_custom: str | None) -> None:
    response = client.request("POST", "/echo", json={"a": 1}, headers=headers)

    payload = response.json()
    assert payload["content_type"] == "application/json"
    assert payload["x_custom"] == expected_x_custom


@pytest.mark.parametrize(
    "kwargs,expected_content_type,expected_body,expected_x_custom",
    [
        pytest.param({}, None, "", None, id="no-body"),
        pytest.param({"data": {"a": "b"}}, "application/x-www-form-urlencoded", "a=b", None, id="form-data"),
        pytest.param({"content": b"raw"}, None, "raw", None, id="raw-content"),
        pytest.param(
            {"data": {"a": "b"}, "headers": {"X-Custom": "yes"}},
            "application/x-www-form-urlencoded",
            "a=b",
            "yes",
            id="form-data-and-headers",
        ),
    ],
)
def test_without_json_arguments_are_passed_through(
    client: JsonTestClient,
    kwargs: dict,
    expected_content_type: str | None,
    expected_body: str,
    expected_x_custom: str | None,
) -> None:
    response = client.request("POST", "/echo", **kwargs)

    payload = response.json()
    assert payload["content_type"] == expected_content_type
    assert payload["body"] == expected_body
    assert payload["x_custom"] == expected_x_custom


def test_json_does_not_emit_deprecation_warnings(client: JsonTestClient) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        response = client.request("POST", "/echo", json={"a": 1})

    assert response.status_code == 200

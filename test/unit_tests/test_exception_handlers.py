# Copyright 2019-2020 SURF.
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

"""Tests for problem_detail_handler: conditional title/type inclusion, status codes, and header passthrough."""

import json
from unittest.mock import MagicMock

import pytest
from starlette.responses import JSONResponse

from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.exception_handlers import problem_detail_handler


def _make_exc(status_code: int, detail=None, title=None, error_type=None, headers=None) -> ProblemDetailException:
    return ProblemDetailException(
        status=status_code, title=title, detail=detail, headers=headers, error_type=error_type
    )


@pytest.mark.parametrize(
    "status_code",
    [400, 401, 403, 404, 500],
    ids=["400", "401", "403", "404", "500"],
)
async def test_response_has_correct_status_code(status_code: int) -> None:
    response = await problem_detail_handler(MagicMock(), _make_exc(status_code))
    assert isinstance(response, JSONResponse)
    assert response.status_code == status_code


@pytest.mark.parametrize(
    "title,error_type,expected_keys",
    [
        pytest.param("My Title", "my_type", {"title", "type", "detail", "status"}, id="title-and-type"),
        pytest.param("My Title", None, {"title", "detail", "status"}, id="title-only"),
        pytest.param(None, "my_type", {"type", "detail", "status"}, id="type-only"),
        pytest.param(None, None, {"detail", "status"}, id="neither"),
    ],
)
async def test_body_keys_match_provided_fields(title: str | None, error_type: str | None, expected_keys: set) -> None:
    exc = _make_exc(400, title=title, error_type=error_type)
    body = json.loads((await problem_detail_handler(MagicMock(), exc)).body)
    assert set(body.keys()) == expected_keys


async def test_headers_passed_through() -> None:
    exc = _make_exc(401, headers={"WWW-Authenticate": "Bearer"})
    response = await problem_detail_handler(MagicMock(), exc)
    assert response.headers["www-authenticate"] == "Bearer"


async def test_detail_defaults_to_status_phrase() -> None:
    body = json.loads((await problem_detail_handler(MagicMock(), _make_exc(400))).body)
    assert body["detail"] == "Bad Request"

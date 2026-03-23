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

import json
from unittest.mock import MagicMock

import pytest
from starlette.responses import JSONResponse

from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.exception_handlers import problem_detail_handler


def make_exc(status_code: int, detail=None, title=None, error_type=None, headers=None) -> ProblemDetailException:
    return ProblemDetailException(
        status=status_code, title=title, detail=detail, headers=headers, error_type=error_type
    )


def parse_body(response: JSONResponse) -> dict:
    return json.loads(response.body)


class TestProblemDetailHandler:
    async def test_returns_json_response(self):
        exc = make_exc(400)
        response = await problem_detail_handler(MagicMock(), exc)
        assert isinstance(response, JSONResponse)

    @pytest.mark.parametrize(
        "status_code",
        [400, 401, 403, 404, 500],
        ids=["400", "401", "403", "404", "500"],
    )
    async def test_response_has_correct_status_code(self, status_code):
        exc = make_exc(status_code)
        response = await problem_detail_handler(MagicMock(), exc)
        assert response.status_code == status_code

    async def test_body_contains_detail_and_status(self):
        exc = make_exc(404, detail="Not found")
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert body["detail"] == "Not found"
        assert body["status"] == 404

    async def test_body_detail_is_status_phrase_when_not_set(self):
        # FastAPI's HTTPException fills detail with the HTTP phrase when detail=None is passed.
        exc = make_exc(400)
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert body["detail"] == "Bad Request"

    async def test_title_included_when_present(self):
        exc = make_exc(400, title="Bad Request")
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert body["title"] == "Bad Request"

    async def test_type_included_when_present(self):
        exc = make_exc(400, error_type="validation_error")
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert body["type"] == "validation_error"

    async def test_title_excluded_when_none(self):
        exc = make_exc(400, title=None)
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert "title" not in body

    async def test_type_excluded_when_none(self):
        exc = make_exc(400, error_type=None)
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert "type" not in body

    async def test_headers_passed_through_when_present(self):
        exc = make_exc(401, headers={"WWW-Authenticate": "Bearer"})
        response = await problem_detail_handler(MagicMock(), exc)
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_no_extra_headers_when_headers_none(self):
        exc = make_exc(400, headers=None)
        response = await problem_detail_handler(MagicMock(), exc)
        # Default JSONResponse always has content-type; no extra custom headers
        assert "www-authenticate" not in response.headers

    async def test_all_fields_included_together(self):
        exc = make_exc(422, detail="Unprocessable", title="Unprocessable Entity", error_type="validation_error")
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert body["status"] == 422
        assert body["detail"] == "Unprocessable"
        assert body["title"] == "Unprocessable Entity"
        assert body["type"] == "validation_error"

    @pytest.mark.parametrize(
        "title, error_type, expected_keys",
        [
            ("My Title", "my_type", {"title", "type", "detail", "status"}),
            ("My Title", None, {"title", "detail", "status"}),
            (None, "my_type", {"type", "detail", "status"}),
            (None, None, {"detail", "status"}),
        ],
        ids=["title_and_type", "title_only", "type_only", "neither"],
    )
    async def test_body_keys_match_provided_fields(self, title, error_type, expected_keys):
        exc = make_exc(400, title=title, error_type=error_type)
        response = await problem_detail_handler(MagicMock(), exc)
        body = parse_body(response)
        assert set(body.keys()) == expected_keys

    async def test_request_argument_is_not_used(self):
        """Handler should work regardless of the request object passed."""
        exc = make_exc(500, detail="Server Error")
        response = await problem_detail_handler(None, exc)  # type: ignore[arg-type]
        assert response.status_code == 500

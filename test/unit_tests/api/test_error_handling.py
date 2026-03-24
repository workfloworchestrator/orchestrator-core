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

from http import HTTPStatus

import pytest
from fastapi.exceptions import HTTPException
from starlette.datastructures import MutableHeaders

from orchestrator.api.error_handling import ProblemDetailException, raise_status


class TestProblemDetailException:
    def test_is_subclass_of_http_exception(self):
        exc = ProblemDetailException(status=400)
        assert isinstance(exc, HTTPException)

    def test_status_code_set_correctly(self):
        exc = ProblemDetailException(status=404)
        assert exc.status_code == 404

    def test_title_set_correctly(self):
        exc = ProblemDetailException(status=400, title="Bad Request")
        assert exc.title == "Bad Request"

    def test_detail_set_correctly(self):
        exc = ProblemDetailException(status=400, detail="Something went wrong")
        assert exc.detail == "Something went wrong"

    def test_error_type_maps_to_type_attribute(self):
        exc = ProblemDetailException(status=400, error_type="validation_error")
        assert exc.type == "validation_error"

    def test_headers_set_correctly(self):
        exc = ProblemDetailException(status=401, headers={"WWW-Authenticate": "Bearer"})
        assert exc.headers == {"WWW-Authenticate": "Bearer"}

    def test_default_headers_is_empty_dict_when_none_passed(self):
        exc = ProblemDetailException(status=400, headers=None)
        assert exc.headers == {}

    def test_all_defaults_are_none_or_empty(self):
        # FastAPI's HTTPException fills detail with the status phrase when None is passed,
        # so we verify the orchestrator-specific fields default to None/empty.
        exc = ProblemDetailException(status=200)
        assert exc.title is None
        assert exc.type is None
        assert exc.headers == {}

    def test_detail_can_be_dict(self):
        detail = {"field": "value", "error": "invalid"}
        exc = ProblemDetailException(status=422, detail=detail)
        assert exc.detail == detail

    def test_detail_can_be_list(self):
        detail = ["error1", "error2"]
        exc = ProblemDetailException(status=422, detail=detail)
        assert exc.detail == detail


class TestRaiseStatus:
    @pytest.mark.parametrize(
        "status_code, expected_phrase",
        [
            (400, "Bad Request"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Not Found"),
            (500, "Internal Server Error"),
        ],
        ids=["400", "401", "403", "404", "500"],
    )
    def test_raises_problem_detail_exception_with_correct_status_and_phrase(self, status_code, expected_phrase):
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(status_code)
        assert exc_info.value.status_code == status_code
        assert exc_info.value.title == expected_phrase

    def test_detail_passed_through(self):
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(404, detail="Resource not found")
        assert exc_info.value.detail == "Resource not found"

    def test_none_headers_are_accepted(self):
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(400, headers=None)
        assert exc_info.value.headers == {}

    def test_dict_headers_passed_through(self):
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(401, headers={"WWW-Authenticate": "Bearer"})
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_mutable_headers_converted_to_dict(self):
        mutable = MutableHeaders(headers={"X-Custom": "value"})
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(400, headers=mutable)
        assert isinstance(exc_info.value.headers, dict)
        assert exc_info.value.headers["x-custom"] == "value"

    def test_title_is_http_status_phrase(self):
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(HTTPStatus.NOT_FOUND)
        assert exc_info.value.title == HTTPStatus.NOT_FOUND.phrase

    def test_detail_is_status_phrase_when_not_provided(self):
        # FastAPI's HTTPException fills detail with the HTTP phrase when detail=None is passed.
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(400)
        assert exc_info.value.detail == HTTPStatus(400).phrase

    def test_raise_status_with_integer_status(self):
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(404)
        assert exc_info.value.status_code == 404
        assert exc_info.value.title == "Not Found"

    def test_raise_status_detail_defaults_to_http_phrase_when_none(self):
        with pytest.raises(ProblemDetailException) as exc_info:
            raise_status(503)
        assert exc_info.value.detail == HTTPStatus(503).phrase


class TestProblemDetailExceptionAllParameters:
    def test_all_parameters_set_at_once(self):
        exc = ProblemDetailException(
            status=403,
            title="Forbidden",
            detail="You do not have permission",
            headers={"X-Reason": "forbidden"},
            error_type="permission_denied",
        )
        assert exc.status_code == 403
        assert exc.title == "Forbidden"
        assert exc.detail == "You do not have permission"
        assert exc.headers == {"X-Reason": "forbidden"}
        assert exc.type == "permission_denied"

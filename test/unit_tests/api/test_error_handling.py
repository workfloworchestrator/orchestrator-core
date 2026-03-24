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

"""Tests for ProblemDetailException (None-headers default, error_type mapping) and raise_status (MutableHeaders conversion, title derivation)."""


import pytest
from starlette.datastructures import MutableHeaders

from orchestrator.api.error_handling import ProblemDetailException, raise_status


def test_none_headers_defaults_to_empty_dict() -> None:
    exc = ProblemDetailException(status=400, headers=None)
    assert exc.headers == {}


def test_error_type_maps_to_type_attribute() -> None:
    exc = ProblemDetailException(status=400, error_type="validation_error")
    assert exc.type == "validation_error"


@pytest.mark.parametrize(
    "status_code,expected_phrase",
    [
        pytest.param(400, "Bad Request", id="400"),
        pytest.param(404, "Not Found", id="404"),
        pytest.param(503, "Service Unavailable", id="503"),
    ],
)
def test_raise_status_sets_title_from_http_phrase(status_code: int, expected_phrase: str) -> None:
    with pytest.raises(ProblemDetailException) as exc_info:
        raise_status(status_code)
    assert exc_info.value.title == expected_phrase


def test_raise_status_passes_detail_through() -> None:
    with pytest.raises(ProblemDetailException) as exc_info:
        raise_status(404, detail="Resource not found")
    assert exc_info.value.detail == "Resource not found"


def test_raise_status_converts_mutable_headers_to_dict() -> None:
    mutable = MutableHeaders(headers={"X-Custom": "value"})
    with pytest.raises(ProblemDetailException) as exc_info:
        raise_status(400, headers=mutable)
    assert isinstance(exc_info.value.headers, dict)
    assert exc_info.value.headers["x-custom"] == "value"

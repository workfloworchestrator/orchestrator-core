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

from http import HTTPStatus

from orchestrator.core.utils.errors import ApiException, ProcessFailureError, error_state_to_dict


class RESTResponse:  # From openapi-generator generated clients
    def __init__(self, status, reason, data, headers):
        self.status = status
        self.reason = reason
        self.data = data
        self.headers = headers

    def getheaders(self):
        """Return a dictionary of the response headers."""
        return self.headers


def test_error_state_to_dict_base_exception():
    e = Exception("bla")
    assert error_state_to_dict(e) == {
        "class": "Exception",
        "error": "bla",
        "traceback": "Exception: bla\n",
    }


def test_error_state_to_dict_api_exception():
    e = ApiException(status=HTTPStatus.NOT_FOUND, reason="Not Found")
    assert error_state_to_dict(e) == {
        "body": None,
        "class": "ApiException",
        "error": "Not Found",
        "headers": "",
        "status_code": HTTPStatus.NOT_FOUND,
        "traceback": "ApiException: (404)\nReason: Not Found\n\n",
    }


def test_error_state_to_dict_api_exception_with_http_response():
    e = ApiException(
        http_resp=RESTResponse(HTTPStatus.NOT_FOUND, "Not Found", "Body", {"Header": "value", "Content-type": "bogus"})
    )
    assert error_state_to_dict(e) == {
        "body": "Body",
        "class": "ApiException",
        "error": "Not Found",
        "headers": "Header: value\nContent-type: bogus",
        "status_code": HTTPStatus.NOT_FOUND,
        "traceback": "ApiException: (404)\nReason: Not Found\nHTTP response headers: {'Header': 'value', 'Content-type': 'bogus'}\nHTTP response body: Body\n\n",
    }


def test_error_state_to_dict_api_exception_with_headers_none():
    e = ApiException(status=HTTPStatus.NOT_FOUND, reason="Not Found")
    e.headers = None
    assert error_state_to_dict(e) == {
        "body": None,
        "class": "ApiException",
        "error": "Not Found",
        "headers": "",
        "status_code": HTTPStatus.NOT_FOUND,
        "traceback": "ApiException: (404)\nReason: Not Found\n\n",
    }


def test_error_state_to_dict_process_failure_exception():
    e = ProcessFailureError(message="Something went wrong", details={"foo": "bar"})
    assert error_state_to_dict(e) == {
        "class": "ProcessFailureError",
        "details": {"foo": "bar"},
        "error": "Something went wrong",
        "traceback": "ProcessFailureError: ('Something went wrong', {'foo': 'bar'})\n",
    }

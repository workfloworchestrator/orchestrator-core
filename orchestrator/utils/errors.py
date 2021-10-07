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
from typing import Dict, Optional, cast

import structlog
from nwastdlib.ex import show_ex

from orchestrator.types import JSON, ErrorDict

logger = structlog.get_logger(__name__)


class ApiException(Exception):
    """Api Exception Class.

    This is a copy of what is generated in api_clients. We use this to have consistent error handling for nso to.
    This should conform to what is used in the api clients.
    """

    status: Optional[HTTPStatus]
    reason: Optional[str]
    body: Optional[str]
    headers: Dict[str, str]

    def __init__(
        self, status: Optional[HTTPStatus] = None, reason: Optional[str] = None, http_resp: Optional[object] = None
    ):
        super().__init__(status, reason, http_resp)
        if http_resp:
            self.status = http_resp.status  # type:ignore
            self.reason = http_resp.reason  # type:ignore
            self.body = http_resp.data  # type:ignore
            self.headers = http_resp.getheaders()  # type:ignore
        else:
            self.status = status
            self.reason = reason
            self.body = None
            self.headers = {}

    def __str__(self) -> str:
        """Create custom error messages for exception."""
        error_message = "({})\n" "Reason: {}\n".format(self.status, self.reason)
        if self.headers:
            error_message += f"HTTP response headers: {self.headers}\n"

        if self.body:
            error_message += f"HTTP response body: {self.body}\n"

        return error_message


class ProcessFailure(Exception):
    message: str
    details: JSON

    def __init__(self, message: str, details: JSON = None) -> None:
        super().__init__(message, details)
        self.message = message
        self.details = details


class InconsistentData(ProcessFailure):
    pass


def is_api_exception(ex: Exception) -> bool:
    """Test for swagger-codegen ApiException.

    For each API, swagger-codegen generates a new ApiException class. These are not organized into
    a hierarchy. Hence testing whether one is dealing with one of the ApiException classes without knowing how
    many there are and where they are located, needs some special logic.

    Args:
        ex: the Exception to be tested.

    Returns:
        True if it is an ApiException, False otherwise.

    """
    return ex.__class__.__name__ == "ApiException"


def error_state_to_dict(err: Exception) -> ErrorDict:
    """Return an ErrorDict based on the exception.

    Args:
        err: Exception
    Returns:
        An ErrorDict containing the error message a status_code and a traceback if available

    """
    if isinstance(err, ProcessFailure):
        return {"class": type(err).__name__, "error": err.message, "traceback": show_ex(err), "details": err.details}
    elif is_api_exception(err):
        err = cast(ApiException, err)
        return {
            "class": type(err).__name__,
            "error": err.reason,
            "status_code": err.status,
            "body": err.body,
            "headers": "\n".join(f"{k}: {v}" for k, v in err.headers.items()),
            "traceback": show_ex(err),
        }
    else:
        return {"class": type(err).__name__, "error": str(err), "traceback": show_ex(err)}

# Copyright 2019-2020 SURF, GÉANT.
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

from functools import singledispatch
from http import HTTPStatus
from typing import Any, cast

import structlog

from nwastdlib.ex import show_ex
from orchestrator.types import ErrorDict
from pydantic_forms.types import JSON

logger = structlog.get_logger(__name__)


class ApiException(Exception):  # noqa: N818
    """Api Exception Class.

    This is a copy of what is generated in api_clients. We use this to have consistent error handling for nso to.
    This should conform to what is used in the api clients.
    """

    status: HTTPStatus | None
    reason: str | None
    body: str | None
    headers: dict[str, str]

    def __init__(self, status: HTTPStatus | None = None, reason: str | None = None, http_resp: object | None = None):
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


class ProcessFailureError(Exception):
    message: str
    details: JSON

    def __init__(self, message: str, details: JSON = None) -> None:
        super().__init__(message, details)
        self.message = message
        self.details = details


class InconsistentDataError(ProcessFailureError):
    pass


class StaleDataError(ValueError):
    """The version of the update payload does not match the version in the database."""

    def __init__(self, current_version: int, new_version: int | None = None) -> None:
        message = f"Stale data: given version ({new_version}) does not match the current version ({current_version})"
        super().__init__(message)


def is_api_exception(ex: Exception) -> bool:
    """Test for swagger-codegen ApiException.

    For each API, swagger-codegen generates a new ApiException class. These are not organized into
    a hierarchy. Hence, testing whether one is dealing with one of the ApiException classes without knowing how
    many there are and where they are located, needs some special logic.

    Args:
        ex: the Exception to be tested.

    Returns:
        True if it is an ApiException, False otherwise.

    """
    return ex.__class__.__name__ == "ApiException"


@singledispatch
def error_state_to_dict(err: Any) -> ErrorDict:
    """Return an ErrorDict based on the passed error object.

    Args:
        err: An error object like an Exception, Error or ErrorDict
    Returns:
        An ErrorDict containing the error message a status_code and a traceback if available

    """
    raise NotImplementedError(f"Unsupported error state type: {type(err)}")


@error_state_to_dict.register(dict)
def _(err: ErrorDict) -> ErrorDict:
    return err


@error_state_to_dict.register
def _(err: ProcessFailureError) -> ErrorDict:
    return {"class": type(err).__name__, "error": err.message, "traceback": show_ex(err), "details": err.details}


@error_state_to_dict.register
def _(err: Exception) -> ErrorDict:
    # We can't dispatch on ApiException, see is_api_exception docstring
    if is_api_exception(err):
        err = cast(ApiException, err)
        return {
            "class": type(err).__name__,
            "error": err.reason,
            "status_code": err.status,
            "body": err.body,
            "headers": "\n".join(f"{k}: {v}" for k, v in err.headers.items()),
            "traceback": show_ex(err),
        }

    return {"class": type(err).__name__, "error": str(err), "traceback": show_ex(err)}

# Copyright 2019-2023 SURF.
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
from collections.abc import Collection, Generator, Iterable
from contextvars import ContextVar
from enum import StrEnum, auto
from http import HTTPStatus
from typing import Any

import structlog
from graphql import GraphQLError
from httpx import HTTPStatusError, Response
from strawberry.extensions import SchemaExtension
from strawberry.types import ExecutionContext, Info

logger = structlog.stdlib.get_logger(__name__)

EXTENSION_ERROR_TYPE = "error_type"
EXTENSION_HTTP_STATUS_CODE = "http_status_code"

_error_bucket: ContextVar[None | list[GraphQLError]] = ContextVar("error_bucket", default=None)


class ErrorType(StrEnum):
    """These error types are returned in 'error_type' extension field on an error response.

    https://productionreadygraphql.com/2020-08-01-guide-to-graphql-errors
    https://engineering.zalando.com/posts/2021/04/modeling-errors-in-graphql.html

    We currently distinguish 3 categories that are meaningful to the frontend/user:
     - NOT_AUTHORIZED: user not allowed to access, may be solved by renewing token or a different entitlement
     - NOT_FOUND: a resource wasn't found, data inconsistency or wrong identifier
     - INTERNAL_ERROR: all other errors on the graphql server and/or backend systems. User may retry later
    """

    NOT_AUTHORIZED = auto()
    NOT_FOUND = auto()
    INTERNAL_ERROR = auto()


def _is_http_error(exception: Exception, *statuses: HTTPStatus) -> bool:
    match exception:
        case HTTPStatusError(response=Response(status_code=s)) if s in statuses:
            return True

    return False


def _to_error_type(exception: Exception | None) -> ErrorType:
    # For https://git.ia.surfsara.nl/netdev/automation/projects/orchestrator/-/issues/1892 when we move this extension
    # to a library, we could make it possible to initialize the ErrorHandlerExtension with an additional (custom)
    # ErrorType mapper. Because each GraphQL project will have different exceptions
    match exception:
        case PermissionError():
            return ErrorType.NOT_AUTHORIZED
        case Exception() if _is_http_error(exception, HTTPStatus.FORBIDDEN, HTTPStatus.UNAUTHORIZED):
            return ErrorType.NOT_AUTHORIZED
        case Exception() if _is_http_error(exception, HTTPStatus.NOT_FOUND):
            return ErrorType.NOT_FOUND
        case _:
            return ErrorType.INTERNAL_ERROR


def _get_all_errors(execution_context: ExecutionContext) -> Iterable[GraphQLError]:
    # Errors from strawberry or exceptions raised by our code
    if execution_context.result and execution_context.result.errors:
        yield from execution_context.result.errors

    # Errors registered by our code
    if registered_errors := _error_bucket.get():
        yield from registered_errors


def _has_extension(error: GraphQLError, key: str) -> bool:
    return key in (error.extensions or {})


def _add_extension(error: GraphQLError, key: str, value: Any) -> None:
    if error.extensions is None:
        error.extensions = {}
    error.extensions[key] = value


def _process(error: GraphQLError) -> GraphQLError:
    exc = error.original_error
    if isinstance(exc, HTTPStatusError):
        _add_extension(error, EXTENSION_HTTP_STATUS_CODE, {f"{exc.request.url}": exc.response.status_code})
    if not _has_extension(error, EXTENSION_ERROR_TYPE):
        _add_extension(error, EXTENSION_ERROR_TYPE, str(_to_error_type(exc)))
    return error


class ErrorHandlerExtension(SchemaExtension):
    """Collect all raised and/or registered errors and enriches them with metadata.

    Disambiguation:
    - This class is a Strawberry extension that is executed on each graphql query, like a middleware.
    - The metadata added to each error is also called an 'extension' because it is a reserved field in the GraphQL spec.
    More details: https://spec.graphql.org/October2021/#sec-Errors.Error-result-format
    """

    def on_execute(self) -> Generator[None, None, None]:
        _error_bucket.set([])

        yield

        if not self.execution_context or self.execution_context.result is None:
            return

        self.execution_context.result.errors = [_process(error) for error in _get_all_errors(self.execution_context)]


def _register(message: str, path: Collection[str], error_type: ErrorType) -> None:
    error = GraphQLError(message=message, path=path, extensions={EXTENSION_ERROR_TYPE: str(error_type)})
    if (errors := _error_bucket.get()) is None:
        logger.debug("ErrorHandlerExtension disabled, dropping error", error=error)
        return

    logger.debug("Registering error", error=error)
    errors.append(error)
    _error_bucket.set(errors)


def register_error(message: str, info: Info, error_type: ErrorType = ErrorType.INTERNAL_ERROR) -> None:
    """Register an error message.

    Use this to collect error messages from multiple resolvers and return them in the response.
    """
    _register(message, info.path, error_type)


def register_exception(exception: Exception, info: Info) -> None:
    """Register an exception encountered during the query execution.

    Use this to collect exceptions from multiple resolvers and return them in the response.
    """
    _register(str(exception), info.path, _to_error_type(exception))

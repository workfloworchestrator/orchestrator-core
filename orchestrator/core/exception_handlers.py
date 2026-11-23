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

from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.requests import Request
from starlette.responses import JSONResponse
from structlog import get_logger

from orchestrator.core.api.error_handling import ProblemDetailException
from orchestrator.core.search.query.exceptions import PathNotFoundError, QueryValidationError

logger = get_logger(__name__)

PROBLEM_DETAIL_FIELDS = ("title", "type")

DATABASE_UNAVAILABLE_MESSAGE = "The database connection pool is exhausted. Please try again later."


async def problem_detail_handler(request: Request, exc: ProblemDetailException) -> JSONResponse:
    headers = getattr(exc, "headers", None)

    body: dict = {"detail": exc.detail, "status": exc.status_code}

    for field in PROBLEM_DETAIL_FIELDS:
        value = getattr(exc, field, None)
        if value:
            body[field] = value

    if headers:
        return JSONResponse(body, status_code=exc.status_code, headers=headers)
    return JSONResponse(body, status_code=exc.status_code)


async def query_validation_handler(request: Request, exc: QueryValidationError) -> JSONResponse:
    """Render any search-layer query validation error (bad filter path, operator, etc.) as a 422.

    Keyed on the ``QueryValidationError`` base so every subclass is covered; ``PathNotFoundError``
    additionally points the caller at ``discover_filter_paths`` to find a valid path.
    """
    status = HTTPStatus.UNPROCESSABLE_ENTITY
    detail = str(exc)
    if isinstance(exc, PathNotFoundError):
        detail = f"{detail} Use discover_filter_paths to find valid paths."
    return JSONResponse({"detail": detail, "status": status.value, "title": status.phrase}, status_code=status.value)


async def database_timeout_handler(request: Request, exc: SQLAlchemyTimeoutError) -> JSONResponse:
    """Answer an exhausted connection pool with a 503 instead of an unhandled 500.

    GraphQL returns these in its ``errors`` list instead, since a resolver cannot set a status code.
    """
    logger.warning(
        "Database connection pool exhausted",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    status = HTTPStatus.SERVICE_UNAVAILABLE
    return JSONResponse(
        {"detail": DATABASE_UNAVAILABLE_MESSAGE, "status": status.value, "title": status.phrase},
        status_code=status.value,
        headers={"Retry-After": "5"},
    )

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

from starlette.requests import Request
from starlette.responses import JSONResponse

from orchestrator.core.api.error_handling import ProblemDetailException
from orchestrator.core.search.query.exceptions import PathNotFoundError, QueryValidationError

PROBLEM_DETAIL_FIELDS = ("title", "type")


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

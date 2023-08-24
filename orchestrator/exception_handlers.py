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


from starlette.requests import Request
from starlette.responses import JSONResponse

from orchestrator.api.error_handling import ProblemDetailException

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

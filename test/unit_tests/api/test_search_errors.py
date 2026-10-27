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

import pytest
from fastapi import HTTPException

from orchestrator.core.api.api_v1.endpoints.search import search_errors_to_http
from orchestrator.core.search.core.exceptions import (
    InvalidCursorError,
    InvalidSearchPageError,
    QueryStateNotFoundError,
)
from orchestrator.core.search.query.exceptions import PathNotFoundError


@pytest.mark.parametrize(
    "error, status_code, detail",
    [
        pytest.param(
            InvalidCursorError("Invalid pagination cursor"), HTTPStatus.UNPROCESSABLE_ENTITY, None, id="cursor"
        ),
        pytest.param(InvalidSearchPageError("Missing input"), HTTPStatus.BAD_REQUEST, None, id="missing-input"),
        pytest.param(PathNotFoundError("subscription.x"), HTTPStatus.UNPROCESSABLE_ENTITY, None, id="query-validation"),
        pytest.param(ValueError("Invalid query"), HTTPStatus.UNPROCESSABLE_ENTITY, None, id="value-error"),
        pytest.param(QueryStateNotFoundError("Query not found"), HTTPStatus.NOT_FOUND, None, id="query-not-found"),
        pytest.param(
            HTTPException(HTTPStatus.BAD_REQUEST, "Unsupported query type"),
            HTTPStatus.BAD_REQUEST,
            "Unsupported query type",
            id="http",
        ),
        pytest.param(RuntimeError("boom"), HTTPStatus.INTERNAL_SERVER_ERROR, "Search failed: boom", id="unexpected"),
    ],
)
def test_search_errors_to_http(error, status_code, detail):
    with pytest.raises(HTTPException) as exc_info:
        with search_errors_to_http("Search failed"):
            raise error

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail == (detail or str(error))

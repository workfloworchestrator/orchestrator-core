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
from types import SimpleNamespace
from unittest import mock

import httpx
import pytest
from graphql import GraphQLError

from orchestrator.core.graphql.schema import OrchestratorSchema


def httpx_error(status_code: int) -> Exception:
    request = httpx.Request("GET", "https://example.test/thing")
    return httpx.HTTPStatusError("not found", request=request, response=httpx.Response(status_code, request=request))


def foreign_client_error(status_code: int) -> Exception:
    """Any other client — httpx2 on oauth2-lib 3.x, requests, whatever a resolver reaches for."""
    error = Exception("not found")
    error.response = SimpleNamespace(status_code=status_code)  # type: ignore[attr-defined]
    return error


@pytest.mark.parametrize("make_error", [httpx_error, foreign_client_error], ids=["httpx", "foreign-client"])
@pytest.mark.parametrize(
    ("status_code", "debug_calls", "error_calls"),
    [(HTTPStatus.NOT_FOUND, 1, 0), (HTTPStatus.INTERNAL_SERVER_ERROR, 0, 1)],
)
def test_process_errors_logs_404_at_debug(make_error, status_code, debug_calls, error_calls):
    """A 404 is noise whichever client raised it; anything else is a real error.

    Resolvers pick their own HTTP client, so this must not depend on the exception's class.
    """
    error = GraphQLError("boom", original_error=make_error(status_code))

    with mock.patch("orchestrator.core.graphql.schema.StrawberryLogger") as logger:
        OrchestratorSchema.process_errors(mock.MagicMock(), [error])

    assert logger.logger.debug.call_count == debug_calls
    assert logger.error.call_count == error_calls


def test_process_errors_reports_error_without_response():
    error = GraphQLError("boom", original_error=ValueError("no response attribute"))

    with mock.patch("orchestrator.core.graphql.schema.StrawberryLogger") as logger:
        OrchestratorSchema.process_errors(mock.MagicMock(), [error])

    logger.error.assert_called_once()

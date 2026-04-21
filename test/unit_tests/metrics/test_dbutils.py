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

import pytest
from orchestrator.metrics.dbutils import handle_missing_tables
from psycopg import errors as psycopg_errors
from sqlalchemy.exc import ProgrammingError


def test_handle_missing_tables_passes_through_normally() -> None:
    """No exception inside the block: context manager exits cleanly."""
    result = []
    with handle_missing_tables():
        result.append("executed")
    assert result == ["executed"]


def test_handle_missing_tables_suppresses_undefined_table_error() -> None:
    """ProgrammingError wrapping UndefinedTable is caught and not re-raised."""
    orig = psycopg_errors.UndefinedTable()
    exc = ProgrammingError("", {}, orig)

    with handle_missing_tables():
        raise exc  # must not propagate


@pytest.mark.parametrize(
    "orig",
    [
        pytest.param(Exception("other error"), id="generic-exception"),
        pytest.param(ValueError("bad value"), id="value-error"),
    ],
)
def test_handle_missing_tables_reraises_other_programming_errors(orig: Exception) -> None:
    """ProgrammingError wrapping anything other than UndefinedTable is re-raised."""
    exc = ProgrammingError("", {}, orig)

    with pytest.raises(ProgrammingError) as exc_info:
        with handle_missing_tables():
            raise exc

    assert exc_info.value is exc

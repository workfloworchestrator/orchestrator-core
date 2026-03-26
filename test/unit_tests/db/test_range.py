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

"""Tests for range helpers: apply_range_to_statement (LIMIT/OFFSET, validation) and apply_range_to_query (offset/limit+1 logic)."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import column, select, table

from orchestrator.db.range.range import apply_range_to_query, apply_range_to_statement


def _make_stmt():
    return select(table("items", column("id")))


# --- apply_range_to_statement ---


@pytest.mark.parametrize(
    "start,end",
    [
        pytest.param(0, 10, id="zero-to-ten"),
        pytest.param(5, 15, id="mid-range"),
        pytest.param(0, 1, id="minimal"),
    ],
)
def test_apply_range_to_statement_valid(start: int, end: int) -> None:
    result = apply_range_to_statement(_make_stmt(), start, end)
    assert result is not None


@pytest.mark.parametrize(
    "start,end",
    [
        pytest.param(10, 5, id="start-gt-end"),
        pytest.param(5, 5, id="start-eq-end"),
    ],
)
def test_apply_range_to_statement_invalid_raises(start: int, end: int) -> None:
    with pytest.raises(ValueError, match="range start must be lower than end"):
        apply_range_to_statement(_make_stmt(), start, end)


# --- apply_range_to_query ---


def _make_query():
    query = MagicMock()
    limited = MagicMock()
    offsetted = MagicMock()
    offsetted.limit.return_value = limited
    query.offset.return_value = offsetted
    return query, offsetted, limited


@pytest.mark.parametrize(
    "offset,limit,expected_limit_arg",
    [
        pytest.param(0, 1, 2, id="minimal"),
        pytest.param(10, 5, 6, id="mid-range"),
        pytest.param(0, 100, 101, id="large"),
    ],
)
def test_apply_range_to_query_increments_limit(offset: int, limit: int, expected_limit_arg: int) -> None:
    query, offsetted, _ = _make_query()
    apply_range_to_query(query, offset=offset, limit=limit)
    query.offset.assert_called_once_with(offset)
    offsetted.limit.assert_called_once_with(expected_limit_arg)


@pytest.mark.parametrize(
    "offset,limit",
    [
        pytest.param(None, 10, id="none-offset"),
        pytest.param(0, 0, id="zero-limit"),
        pytest.param(0, None, id="none-limit"),
        pytest.param(None, None, id="both-none"),
    ],
)
def test_apply_range_to_query_skips_when_falsy(offset: int | None, limit: int | None) -> None:
    query, _, _ = _make_query()
    result = apply_range_to_query(query, offset=offset or 0, limit=limit or 0)
    query.offset.assert_not_called()
    assert result == query

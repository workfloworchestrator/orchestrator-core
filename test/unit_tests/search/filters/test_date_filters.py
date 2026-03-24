"""Tests for orchestrator.search.filters.date_filters: date string validation, DateRange, DateValueFilter, and DateRangeFilter."""

# Copyright 2019-2025 SURF, GÉANT.
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

from datetime import date, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import String, column
from sqlalchemy.sql.elements import ColumnElement

from orchestrator.search.core.types import FilterOp
from orchestrator.search.filters.date_filters import (
    DateRange,
    DateRangeFilter,
    DateValueFilter,
    _validate_date_string,
)

pytestmark = pytest.mark.search

_col = column("value", String)

_COMPARISON_OPS_AND_SQL = [
    pytest.param(FilterOp.EQ, "=", id="eq"),
    pytest.param(FilterOp.NEQ, "!=", id="neq"),
    pytest.param(FilterOp.LT, "<", id="lt"),
    pytest.param(FilterOp.LTE, "<=", id="lte"),
    pytest.param(FilterOp.GT, ">", id="gt"),
    pytest.param(FilterOp.GTE, ">=", id="gte"),
]


# ---------------------------------------------------------------------------
# _validate_date_string
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("2025-01-01", id="date-only"),
        pytest.param("2025-06-15T12:00:00", id="datetime"),
        pytest.param("2025-12-31T23:59:59.999999", id="datetime-micros"),
        pytest.param("2000-02-28", id="leap-adj"),
        pytest.param("2025-01-01T00:00:00+00:00", id="datetime-tz"),
    ],
)
def test_validate_date_string_valid_iso_strings_pass_through(value: str) -> None:
    result = _validate_date_string(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("not-a-date", id="text"),
        pytest.param("2025/01/01", id="slash-sep"),
        pytest.param("01-01-2025", id="day-first"),
        pytest.param("2025-13-01", id="invalid-month"),
        pytest.param("", id="empty"),
    ],
)
def test_validate_date_string_invalid_iso_strings_raise_value_error(value: str) -> None:
    with pytest.raises(ValueError, match="ISO-8601"):
        _validate_date_string(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(42, id="int"),
        pytest.param(3.14, id="float"),
        pytest.param(datetime(2025, 1, 1), id="datetime-obj"),
        pytest.param(date(2025, 6, 15), id="date-obj"),
        pytest.param(None, id="none"),
        pytest.param(True, id="bool"),
    ],
)
def test_validate_date_string_non_string_passes_through_unchanged(value: object) -> None:
    result = _validate_date_string(value)
    assert result is value


# ---------------------------------------------------------------------------
# DateRange validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start, end",
    [
        pytest.param("2025-01-01", "2025-12-31", id="full-year"),
        pytest.param("2020-06-01", "2025-06-01", id="multi-year"),
        pytest.param("2025-01-01T00:00:00", "2025-01-02T00:00:00", id="datetime-precision"),
    ],
)
def test_date_range_valid_constructs(start: str, end: str) -> None:
    r = DateRange(start=start, end=end)
    assert r.start == start
    assert r.end == end


@pytest.mark.parametrize(
    "start, end",
    [
        pytest.param("2025-12-31", "2025-01-01", id="reversed"),
        pytest.param("2025-06-15", "2025-06-15", id="equal"),
        pytest.param("2025-01-02", "2025-01-01", id="one-day-before"),
    ],
)
def test_date_range_reversed_raises_validation_error(start: str, end: str) -> None:
    with pytest.raises(ValidationError, match="'to' must be after 'from'"):
        DateRange(start=start, end=end)


@pytest.mark.parametrize(
    "start, end",
    [
        pytest.param("not-a-date", "2025-12-31", id="invalid-start"),
        pytest.param("2025-01-01", "not-a-date", id="invalid-end"),
    ],
)
def test_date_range_invalid_date_raises_validation_error(start: str, end: str) -> None:
    with pytest.raises(ValidationError):
        DateRange(start=start, end=end)


# ---------------------------------------------------------------------------
# DateValueFilter — construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(FilterOp.EQ, id="eq"),
        pytest.param(FilterOp.NEQ, id="neq"),
        pytest.param(FilterOp.LT, id="lt"),
        pytest.param(FilterOp.LTE, id="lte"),
        pytest.param(FilterOp.GT, id="gt"),
        pytest.param(FilterOp.GTE, id="gte"),
    ],
)
def test_date_value_filter_valid_ops_construct(op: FilterOp) -> None:
    f = DateValueFilter(op=op, value="2025-06-15")  # type: ignore[arg-type]
    assert f.op == op
    assert f.value == "2025-06-15"


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(FilterOp.BETWEEN, id="between"),
        pytest.param(FilterOp.LIKE, id="like"),
    ],
)
def test_date_value_filter_invalid_ops_raise(op: FilterOp) -> None:
    with pytest.raises(ValidationError):
        DateValueFilter(op=op, value="2025-06-15")  # type: ignore[arg-type]


def test_date_value_filter_invalid_date_string_raises() -> None:
    with pytest.raises(ValidationError):
        DateValueFilter(op=FilterOp.EQ, value="not-a-date")


# ---------------------------------------------------------------------------
# DateValueFilter — to_expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op, sql_op", _COMPARISON_OPS_AND_SQL)
def test_date_value_filter_to_expression_uses_timestamp_cast(op: FilterOp, sql_op: str) -> None:
    f = DateValueFilter(op=op, value="2025-06-15")  # type: ignore[arg-type]
    expr = f.to_expression(_col, "path")
    assert isinstance(expr, ColumnElement)
    sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert "TIMESTAMP" in sql.upper()
    assert sql_op in sql


# ---------------------------------------------------------------------------
# DateRangeFilter — construction
# ---------------------------------------------------------------------------


def test_date_range_filter_valid_range_constructs() -> None:
    f = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start="2025-01-01", end="2025-12-31"))
    assert f.op == FilterOp.BETWEEN
    assert f.value.start == "2025-01-01"
    assert f.value.end == "2025-12-31"


def test_date_range_filter_invalid_op_raises() -> None:
    with pytest.raises(ValidationError):
        DateRangeFilter(op=FilterOp.EQ, value=DateRange(start="2025-01-01", end="2025-12-31"))  # type: ignore[arg-type]


def test_date_range_filter_reversed_range_raises() -> None:
    with pytest.raises(ValidationError):
        DateRange(start="2025-12-31", end="2025-01-01")


# ---------------------------------------------------------------------------
# DateRangeFilter — to_expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start, end",
    [
        pytest.param("2025-01-01", "2025-12-31", id="within-year"),
        pytest.param("2020-01-01", "2021-01-01", id="across-year"),
    ],
)
def test_date_range_filter_between_returns_and_expression(start: str, end: str) -> None:
    f = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start=start, end=end))
    expr = f.to_expression(_col, "path")
    assert isinstance(expr, ColumnElement)
    sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert "TIMESTAMP" in sql.upper()
    assert ">=" in sql
    # end uses strict < not <=
    assert " < " in sql
    assert "<=" not in sql


def test_date_range_filter_between_sql_contains_start_and_end_values() -> None:
    f = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start="2025-03-01", end="2025-09-30"))
    expr = f.to_expression(_col, "path")
    sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert "2025-03-01" in sql
    assert "2025-09-30" in sql

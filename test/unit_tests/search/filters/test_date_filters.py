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


# ---------------------------------------------------------------------------
# _validate_date_string
# ---------------------------------------------------------------------------


class TestValidateDateString:
    @pytest.mark.parametrize(
        "value",
        [
            "2025-01-01",
            "2025-06-15T12:00:00",
            "2025-12-31T23:59:59.999999",
            "2000-02-28",
            "2025-01-01T00:00:00+00:00",
        ],
        ids=["date-only", "datetime", "datetime-micros", "leap-adj", "datetime-tz"],
    )
    def test_valid_iso_strings_pass_through(self, value: str) -> None:
        result = _validate_date_string(value)
        assert result == value

    @pytest.mark.parametrize(
        "value",
        [
            "not-a-date",
            "2025/01/01",
            "01-01-2025",
            "2025-13-01",
            "",
        ],
        ids=["text", "slash-sep", "day-first", "invalid-month", "empty"],
    )
    def test_invalid_iso_strings_raise_value_error(self, value: str) -> None:
        with pytest.raises(ValueError, match="ISO-8601"):
            _validate_date_string(value)

    @pytest.mark.parametrize(
        "value",
        [
            42,
            3.14,
            datetime(2025, 1, 1),
            date(2025, 6, 15),
            None,
            True,
        ],
        ids=["int", "float", "datetime-obj", "date-obj", "none", "bool"],
    )
    def test_non_string_passes_through_unchanged(self, value: object) -> None:
        result = _validate_date_string(value)
        assert result is value


# ---------------------------------------------------------------------------
# DateRange validation
# ---------------------------------------------------------------------------


class TestDateRange:
    @pytest.mark.parametrize(
        "start, end",
        [
            ("2025-01-01", "2025-12-31"),
            ("2020-06-01", "2025-06-01"),
            ("2025-01-01T00:00:00", "2025-01-02T00:00:00"),
        ],
        ids=["full-year", "multi-year", "datetime-precision"],
    )
    def test_valid_range_constructs(self, start: str, end: str) -> None:
        r = DateRange(start=start, end=end)
        assert r.start == start
        assert r.end == end

    @pytest.mark.parametrize(
        "start, end",
        [
            ("2025-12-31", "2025-01-01"),
            ("2025-06-15", "2025-06-15"),
            ("2025-01-02", "2025-01-01"),
        ],
        ids=["reversed", "equal", "one-day-before"],
    )
    def test_reversed_range_raises_validation_error(self, start: str, end: str) -> None:
        with pytest.raises(ValidationError, match="'to' must be after 'from'"):
            DateRange(start=start, end=end)

    def test_invalid_start_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            DateRange(start="not-a-date", end="2025-12-31")

    def test_invalid_end_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            DateRange(start="2025-01-01", end="not-a-date")


# ---------------------------------------------------------------------------
# DateValueFilter
# ---------------------------------------------------------------------------


class TestDateValueFilterConstruction:
    @pytest.mark.parametrize(
        "op",
        [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE],
        ids=["eq", "neq", "lt", "lte", "gt", "gte"],
    )
    def test_valid_ops_construct(self, op: FilterOp) -> None:
        f = DateValueFilter(op=op, value="2025-06-15")  # type: ignore[arg-type]
        assert f.op == op
        assert f.value == "2025-06-15"

    @pytest.mark.parametrize(
        "op",
        [FilterOp.BETWEEN, FilterOp.LIKE],
        ids=["between", "like"],
    )
    def test_invalid_ops_raise(self, op: FilterOp) -> None:
        with pytest.raises(ValidationError):
            DateValueFilter(op=op, value="2025-06-15")  # type: ignore[arg-type]

    def test_invalid_date_string_raises(self) -> None:
        with pytest.raises(ValidationError):
            DateValueFilter(op=FilterOp.EQ, value="not-a-date")


class TestDateValueFilterToExpression:
    @pytest.mark.parametrize(
        "op, sql_op",
        [
            (FilterOp.EQ, "="),
            (FilterOp.NEQ, "!="),
            (FilterOp.LT, "<"),
            (FilterOp.LTE, "<="),
            (FilterOp.GT, ">"),
            (FilterOp.GTE, ">="),
        ],
        ids=["eq", "neq", "lt", "lte", "gt", "gte"],
    )
    def test_to_expression_returns_column_element(self, op: FilterOp, sql_op: str) -> None:
        f = DateValueFilter(op=op, value="2025-06-15")  # type: ignore[arg-type]
        expr = f.to_expression(_col, "path")
        assert isinstance(expr, ColumnElement)

    @pytest.mark.parametrize(
        "op, sql_op",
        [
            (FilterOp.EQ, "="),
            (FilterOp.NEQ, "!="),
            (FilterOp.LT, "<"),
            (FilterOp.LTE, "<="),
            (FilterOp.GT, ">"),
            (FilterOp.GTE, ">="),
        ],
        ids=["eq", "neq", "lt", "lte", "gt", "gte"],
    )
    def test_to_expression_uses_timestamp_cast(self, op: FilterOp, sql_op: str) -> None:
        f = DateValueFilter(op=op, value="2025-06-15")  # type: ignore[arg-type]
        expr = f.to_expression(_col, "path")
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "TIMESTAMP" in sql.upper()
        assert sql_op in sql


# ---------------------------------------------------------------------------
# DateRangeFilter
# ---------------------------------------------------------------------------


class TestDateRangeFilterConstruction:
    def test_valid_range_constructs(self) -> None:
        f = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start="2025-01-01", end="2025-12-31"))
        assert f.op == FilterOp.BETWEEN
        assert f.value.start == "2025-01-01"
        assert f.value.end == "2025-12-31"

    def test_invalid_op_raises(self) -> None:
        with pytest.raises(ValidationError):
            DateRangeFilter(op=FilterOp.EQ, value=DateRange(start="2025-01-01", end="2025-12-31"))  # type: ignore[arg-type]

    def test_reversed_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            DateRange(start="2025-12-31", end="2025-01-01")


class TestDateRangeFilterToExpression:
    @pytest.mark.parametrize(
        "start, end",
        [
            ("2025-01-01", "2025-12-31"),
            ("2020-01-01", "2021-01-01"),
        ],
        ids=["within-year", "across-year"],
    )
    def test_between_returns_and_expression(self, start: str, end: str) -> None:
        f = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start=start, end=end))
        expr = f.to_expression(_col, "path")
        assert isinstance(expr, ColumnElement)
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "TIMESTAMP" in sql.upper()
        assert ">=" in sql
        # end uses strict < not <=
        assert " < " in sql
        assert "<=" not in sql

    def test_between_sql_contains_start_and_end_values(self) -> None:
        f = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start="2025-03-01", end="2025-09-30"))
        expr = f.to_expression(_col, "path")
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "2025-03-01" in sql
        assert "2025-09-30" in sql

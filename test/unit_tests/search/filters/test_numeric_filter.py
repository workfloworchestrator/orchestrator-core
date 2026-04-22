"""Tests for orchestrator.core.search.filters.numeric_filter: NumericRange validation, NumericValueFilter construction and SQL generation, and NumericRangeFilter BETWEEN expressions."""

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

import pytest
from pydantic import ValidationError
from sqlalchemy import String, column
from sqlalchemy.sql.elements import ColumnElement

from orchestrator.core.search.core.types import FilterOp
from orchestrator.core.search.filters.numeric_filter import NumericRange, NumericRangeFilter, NumericValueFilter

pytestmark = pytest.mark.search

_col = column("value", String)

_COMPARISON_OPS = [
    pytest.param(FilterOp.EQ, id="eq"),
    pytest.param(FilterOp.NEQ, id="neq"),
    pytest.param(FilterOp.LT, id="lt"),
    pytest.param(FilterOp.LTE, id="lte"),
    pytest.param(FilterOp.GT, id="gt"),
    pytest.param(FilterOp.GTE, id="gte"),
]


# ---------------------------------------------------------------------------
# NumericRange validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start, end",
    [
        pytest.param(1, 10, id="int-basic"),
        pytest.param(0, 1, id="int-boundary"),
        pytest.param(-5, 5, id="int-negative"),
        pytest.param(1.5, 2.5, id="float-basic"),
        pytest.param(0.0, 0.001, id="float-small"),
    ],
)
def test_numeric_range_valid_constructs(start: int | float, end: int | float) -> None:
    r = NumericRange(start=start, end=end)
    assert r.start == start
    assert r.end == end


@pytest.mark.parametrize(
    "start, end",
    [
        pytest.param(10, 1, id="int-reversed"),
        pytest.param(5, 5, id="int-equal"),
        pytest.param(2.5, 1.5, id="float-reversed"),
        pytest.param(0.0, 0.0, id="float-equal"),
    ],
)
def test_numeric_range_invalid_raises_validation_error(start: int | float, end: int | float) -> None:
    with pytest.raises(ValidationError, match="'end' must be greater than 'start'"):
        NumericRange(start=start, end=end)


# ---------------------------------------------------------------------------
# NumericValueFilter — construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", _COMPARISON_OPS)
def test_numeric_value_filter_valid_ops_construct(op: FilterOp) -> None:
    f = NumericValueFilter(op=op, value=42)  # type: ignore[arg-type]
    assert f.op == op
    assert f.value == 42


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(FilterOp.BETWEEN, id="between"),
        pytest.param(FilterOp.LIKE, id="like"),
    ],
)
def test_numeric_value_filter_invalid_ops_raise(op: FilterOp) -> None:
    with pytest.raises(ValidationError):
        NumericValueFilter(op=op, value=42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# NumericValueFilter — to_expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "op, value, sql_op, cast_fragment",
    [
        pytest.param(FilterOp.EQ, 10, "=", "BIGINT", id="eq-int"),
        pytest.param(FilterOp.NEQ, 10, "!=", "BIGINT", id="neq-int"),
        pytest.param(FilterOp.LT, 10, "<", "BIGINT", id="lt-int"),
        pytest.param(FilterOp.LTE, 10, "<=", "BIGINT", id="lte-int"),
        pytest.param(FilterOp.GT, 10, ">", "BIGINT", id="gt-int"),
        pytest.param(FilterOp.GTE, 10, ">=", "BIGINT", id="gte-int"),
        pytest.param(FilterOp.EQ, 3.14, "=", "DOUBLE", id="eq-float"),
        pytest.param(FilterOp.NEQ, 3.14, "!=", "DOUBLE", id="neq-float"),
        pytest.param(FilterOp.LT, 3.14, "<", "DOUBLE", id="lt-float"),
        pytest.param(FilterOp.LTE, 3.14, "<=", "DOUBLE", id="lte-float"),
        pytest.param(FilterOp.GT, 3.14, ">", "DOUBLE", id="gt-float"),
        pytest.param(FilterOp.GTE, 3.14, ">=", "DOUBLE", id="gte-float"),
    ],
)
def test_numeric_value_filter_to_expression_sql(
    op: FilterOp, value: int | float, sql_op: str, cast_fragment: str
) -> None:
    f = NumericValueFilter(op=op, value=value)  # type: ignore[arg-type]
    expr = f.to_expression(_col, "path")
    assert isinstance(expr, ColumnElement)
    sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert cast_fragment in sql.upper()
    assert sql_op in sql


# ---------------------------------------------------------------------------
# NumericRangeFilter — construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start, end",
    [
        pytest.param(1, 10, id="int-range"),
        pytest.param(1.5, 9.9, id="float-range"),
    ],
)
def test_numeric_range_filter_valid_constructs(start: int | float, end: int | float) -> None:
    f = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=start, end=end))
    assert f.op == FilterOp.BETWEEN
    assert f.value.start == start
    assert f.value.end == end


def test_numeric_range_filter_invalid_op_raises() -> None:
    with pytest.raises(ValidationError):
        NumericRangeFilter(op=FilterOp.EQ, value={"start": 1, "end": 10})  # type: ignore[arg-type]


def test_numeric_range_filter_invalid_range_order_raises() -> None:
    with pytest.raises(ValidationError):
        NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=10, end=1))


# ---------------------------------------------------------------------------
# NumericRangeFilter — to_expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start, end, cast_fragment",
    [
        pytest.param(1, 100, "BIGINT", id="int-range"),
        pytest.param(0, 1000000, "BIGINT", id="int-large"),
        pytest.param(1.0, 2.5, "DOUBLE", id="float-range"),
        pytest.param(-1.5, 1.5, "DOUBLE", id="float-negative"),
    ],
)
def test_numeric_range_filter_between_returns_and_expression(
    start: int | float, end: int | float, cast_fragment: str
) -> None:
    f = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=start, end=end))
    expr = f.to_expression(_col, "path")
    assert isinstance(expr, ColumnElement)
    sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert cast_fragment in sql.upper()
    assert ">=" in sql
    assert "<=" in sql


def test_numeric_range_filter_between_contains_both_bounds() -> None:
    f = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=5, end=50))
    expr = f.to_expression(_col, "path")
    sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert "5" in sql
    assert "50" in sql

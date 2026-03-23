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

from orchestrator.search.core.types import FilterOp
from orchestrator.search.filters.numeric_filter import NumericRange, NumericRangeFilter, NumericValueFilter

pytestmark = pytest.mark.search

_col = column("value", String)


# ---------------------------------------------------------------------------
# NumericRange validation
# ---------------------------------------------------------------------------


class TestNumericRange:
    @pytest.mark.parametrize(
        "start, end",
        [
            (1, 10),
            (0, 1),
            (-5, 5),
            (1.5, 2.5),
            (0.0, 0.001),
        ],
        ids=["int-basic", "int-boundary", "int-negative", "float-basic", "float-small"],
    )
    def test_valid_range_constructs(self, start: int | float, end: int | float) -> None:
        r = NumericRange(start=start, end=end)
        assert r.start == start
        assert r.end == end

    @pytest.mark.parametrize(
        "start, end",
        [
            (10, 1),
            (5, 5),
            (2.5, 1.5),
            (0.0, 0.0),
        ],
        ids=["int-reversed", "int-equal", "float-reversed", "float-equal"],
    )
    def test_invalid_range_raises_validation_error(self, start: int | float, end: int | float) -> None:
        with pytest.raises(ValidationError, match="'end' must be greater than 'start'"):
            NumericRange(start=start, end=end)


# ---------------------------------------------------------------------------
# NumericValueFilter
# ---------------------------------------------------------------------------


class TestNumericValueFilterConstruction:
    @pytest.mark.parametrize(
        "op",
        [FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE],
        ids=["eq", "neq", "lt", "lte", "gt", "gte"],
    )
    def test_valid_ops_construct(self, op: FilterOp) -> None:
        f = NumericValueFilter(op=op, value=42)  # type: ignore[arg-type]
        assert f.op == op
        assert f.value == 42

    @pytest.mark.parametrize(
        "op",
        [FilterOp.BETWEEN, FilterOp.LIKE],
        ids=["between", "like"],
    )
    def test_invalid_ops_raise(self, op: FilterOp) -> None:
        with pytest.raises(ValidationError):
            NumericValueFilter(op=op, value=42)  # type: ignore[arg-type]


class TestNumericValueFilterToExpression:
    @pytest.mark.parametrize(
        "op, value, cast_type_fragment",
        [
            (FilterOp.EQ, 10, "BIGINT"),
            (FilterOp.NEQ, 10, "BIGINT"),
            (FilterOp.LT, 10, "BIGINT"),
            (FilterOp.LTE, 10, "BIGINT"),
            (FilterOp.GT, 10, "BIGINT"),
            (FilterOp.GTE, 10, "BIGINT"),
            (FilterOp.EQ, 3.14, "DOUBLE"),
            (FilterOp.NEQ, 3.14, "DOUBLE"),
            (FilterOp.LT, 3.14, "DOUBLE"),
            (FilterOp.LTE, 3.14, "DOUBLE"),
            (FilterOp.GT, 3.14, "DOUBLE"),
            (FilterOp.GTE, 3.14, "DOUBLE"),
        ],
        ids=[
            "eq-int",
            "neq-int",
            "lt-int",
            "lte-int",
            "gt-int",
            "gte-int",
            "eq-float",
            "neq-float",
            "lt-float",
            "lte-float",
            "gt-float",
            "gte-float",
        ],
    )
    def test_to_expression_returns_column_element(
        self, op: FilterOp, value: int | float, cast_type_fragment: str
    ) -> None:
        f = NumericValueFilter(op=op, value=value)  # type: ignore[arg-type]
        expr = f.to_expression(_col, "path")
        assert isinstance(expr, ColumnElement)

    @pytest.mark.parametrize(
        "op, value, sql_op",
        [
            (FilterOp.EQ, 10, "="),
            (FilterOp.NEQ, 10, "!="),
            (FilterOp.LT, 10, "<"),
            (FilterOp.LTE, 10, "<="),
            (FilterOp.GT, 10, ">"),
            (FilterOp.GTE, 10, ">="),
        ],
        ids=["eq", "neq", "lt", "lte", "gt", "gte"],
    )
    def test_to_expression_int_uses_bigint_cast(self, op: FilterOp, value: int, sql_op: str) -> None:
        f = NumericValueFilter(op=op, value=value)  # type: ignore[arg-type]
        expr = f.to_expression(_col, "path")
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "BIGINT" in sql.upper()
        assert sql_op in sql

    @pytest.mark.parametrize(
        "op, value, sql_op",
        [
            (FilterOp.EQ, 3.14, "="),
            (FilterOp.NEQ, 3.14, "!="),
            (FilterOp.LT, 3.14, "<"),
            (FilterOp.LTE, 3.14, "<="),
            (FilterOp.GT, 3.14, ">"),
            (FilterOp.GTE, 3.14, ">="),
        ],
        ids=["eq", "neq", "lt", "lte", "gt", "gte"],
    )
    def test_to_expression_float_uses_double_precision_cast(self, op: FilterOp, value: float, sql_op: str) -> None:
        f = NumericValueFilter(op=op, value=value)  # type: ignore[arg-type]
        expr = f.to_expression(_col, "path")
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "DOUBLE" in sql.upper()
        assert sql_op in sql


# ---------------------------------------------------------------------------
# NumericRangeFilter
# ---------------------------------------------------------------------------


class TestNumericRangeFilterConstruction:
    def test_valid_int_range_constructs(self) -> None:
        f = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=1, end=10))
        assert f.op == FilterOp.BETWEEN
        assert f.value.start == 1
        assert f.value.end == 10

    def test_valid_float_range_constructs(self) -> None:
        f = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=1.5, end=9.9))
        assert f.value.start == 1.5
        assert f.value.end == 9.9

    def test_invalid_op_raises(self) -> None:
        with pytest.raises(ValidationError):
            NumericRangeFilter(op=FilterOp.EQ, value={"start": 1, "end": 10})  # type: ignore[arg-type]

    def test_invalid_range_order_raises(self) -> None:
        with pytest.raises(ValidationError):
            NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=10, end=1))


class TestNumericRangeFilterToExpression:
    @pytest.mark.parametrize(
        "start, end, cast_fragment",
        [
            (1, 100, "BIGINT"),
            (0, 1000000, "BIGINT"),
            (1.0, 2.5, "DOUBLE"),
            (-1.5, 1.5, "DOUBLE"),
        ],
        ids=["int-range", "int-large", "float-range", "float-negative"],
    )
    def test_between_returns_and_expression(self, start: int | float, end: int | float, cast_fragment: str) -> None:
        f = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=start, end=end))
        expr = f.to_expression(_col, "path")
        assert isinstance(expr, ColumnElement)
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert cast_fragment in sql.upper()
        assert ">=" in sql
        assert "<=" in sql

    def test_between_int_contains_both_bounds(self) -> None:
        f = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=5, end=50))
        expr = f.to_expression(_col, "path")
        sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "5" in sql
        assert "50" in sql

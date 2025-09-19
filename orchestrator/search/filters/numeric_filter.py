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

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import DOUBLE_PRECISION, INTEGER, and_
from sqlalchemy import cast as sa_cast
from sqlalchemy.sql.elements import ColumnElement
from typing_extensions import Self

from orchestrator.search.core.types import FilterOp, SQLAColumn


class NumericRange(BaseModel):
    start: int | float
    end: int | float

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.end <= self.start:
            raise ValueError("'end' must be greater than 'start'")
        return self


class NumericValueFilter(BaseModel):
    """A filter for single numeric value comparisons (int or float)."""

    op: Literal[FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE]
    value: int | float

    def to_expression(self, column: SQLAColumn, path: str) -> ColumnElement[bool]:
        cast_type = INTEGER if isinstance(self.value, int) else DOUBLE_PRECISION
        numeric_column: ColumnElement[Any] = sa_cast(column, cast_type)
        match self.op:

            case FilterOp.EQ:
                return numeric_column == self.value
            case FilterOp.NEQ:
                return numeric_column != self.value
            case FilterOp.LT:
                return numeric_column < self.value
            case FilterOp.LTE:
                return numeric_column <= self.value
            case FilterOp.GT:
                return numeric_column > self.value
            case FilterOp.GTE:
                return numeric_column >= self.value


class NumericRangeFilter(BaseModel):
    """A filter for a range of numeric values (int or float)."""

    op: Literal[FilterOp.BETWEEN]
    value: NumericRange

    def to_expression(self, column: SQLAColumn, path: str) -> ColumnElement[bool]:
        cast_type = INTEGER if isinstance(self.value.start, int) else DOUBLE_PRECISION
        numeric_column: ColumnElement[Any] = sa_cast(column, cast_type)
        return and_(numeric_column >= self.value.start, numeric_column <= self.value.end)


NumericFilter = Annotated[NumericValueFilter | NumericRangeFilter, Field(discriminator="op")]

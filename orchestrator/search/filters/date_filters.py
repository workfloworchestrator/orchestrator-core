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
from typing import Annotated, Any, Literal

from dateutil.parser import parse as dt_parse
from pydantic import BaseModel, BeforeValidator, Field, model_validator
from sqlalchemy import TIMESTAMP, and_
from sqlalchemy import cast as sa_cast
from sqlalchemy.sql.elements import ColumnElement

from orchestrator.search.core.types import FilterOp, SQLAColumn


def _validate_date_string(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    try:
        dt_parse(v)
        return v
    except Exception as exc:
        raise ValueError("is not a valid date or datetime string") from exc


DateValue = datetime | date | str
ValidatedDateValue = Annotated[DateValue, BeforeValidator(_validate_date_string)]


class DateRange(BaseModel):

    start: ValidatedDateValue
    end: ValidatedDateValue

    @model_validator(mode="after")
    def _order(self) -> "DateRange":
        to_datetime = dt_parse(str(self.end))
        from_datetime = dt_parse(str(self.start))
        if to_datetime <= from_datetime:
            raise ValueError("'to' must be after 'from'")
        return self


class DateValueFilter(BaseModel):
    """A filter that operates on a single date value."""

    op: Literal[FilterOp.EQ, FilterOp.NEQ, FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE]
    value: ValidatedDateValue

    def to_expression(self, column: SQLAColumn, path: str) -> ColumnElement[bool]:
        date_column = sa_cast(column, TIMESTAMP(timezone=True))
        match self.op:
            case FilterOp.EQ:
                return date_column == self.value
            case FilterOp.NEQ:
                return date_column != self.value
            case FilterOp.LT:
                return date_column < self.value
            case FilterOp.LTE:
                return date_column <= self.value
            case FilterOp.GT:
                return date_column > self.value
            case FilterOp.GTE:
                return date_column >= self.value


class DateRangeFilter(BaseModel):
    """A filter that operates on a range of dates."""

    op: Literal[FilterOp.BETWEEN]
    value: DateRange

    def to_expression(self, column: SQLAColumn, path: str) -> ColumnElement[bool]:
        date_column = sa_cast(column, TIMESTAMP(timezone=True))
        return and_(date_column >= self.value.start, date_column < self.value.end)


DateFilter = Annotated[DateValueFilter | DateRangeFilter, Field(discriminator="op")]

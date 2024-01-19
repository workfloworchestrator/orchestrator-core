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
from collections.abc import Callable
from datetime import datetime
from functools import partial

import pytz
from dateutil.parser import parse
from sqlalchemy import ColumnClause

from orchestrator.db.filters.filters import QueryType
from orchestrator.utils.helpers import to_camel

RANGE_TYPES = {
    "gt": ColumnClause.__gt__,
    "gte": ColumnClause.__ge__,
    "lt": ColumnClause.__lt__,
    "lte": ColumnClause.__le__,
    "ne": ColumnClause.__ne__,
}


def convert_to_date(value: str) -> datetime:
    """Parse iso 8601 date from string to datetime.

    Example date: "2022-07-21T03:40:48+00:00"
    """
    try:
        return parse(value).replace(tzinfo=pytz.UTC)
    except ValueError:
        raise ValueError(f"{value} is not a valid date")


def convert_to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{value} is not a valid integer")


def get_filter_value_convert_function(field: ColumnClause) -> Callable:
    if field.type.python_type == datetime:
        return convert_to_date
    if field.type.python_type == int:
        return convert_to_int
    return lambda x: x


def generic_range_filter(range_type_fn: Callable, field: ColumnClause) -> Callable[[QueryType, str], QueryType]:
    filter_operator = partial(range_type_fn, field)
    convert_filter_value = get_filter_value_convert_function(field)

    def use_filter(query: QueryType, value: str) -> QueryType:
        converted_value = convert_filter_value(value)
        return query.filter(filter_operator(converted_value))

    return use_filter


def generic_range_filters(
    column: ColumnClause, column_alias: str | None = None
) -> dict[str, Callable[[QueryType, str], QueryType]]:
    column_name = to_camel(column_alias or column.name)

    return {
        f"{column_name}{operator.capitalize()}": generic_range_filter(operator_fn, column)
        for operator, operator_fn in RANGE_TYPES.items()
    }

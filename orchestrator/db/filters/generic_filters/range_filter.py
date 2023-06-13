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
from datetime import datetime
from typing import Callable, Optional

import pytz
from dateutil.parser import parse
from sqlalchemy import Column

from orchestrator.db.database import SearchQuery

# from sqlalchemy.sql.expression import ColumnOperators
from orchestrator.utils.helpers import to_camel

range_operator_list = ["gt", "gte", "lt", "lte", "ne"]


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


def get_filter_value_convert_function(field: Column) -> Callable:
    if field.type.python_type == datetime:
        return convert_to_date
    if field.type.python_type == int:
        return convert_to_int
    return lambda x: x


def get_range_filter(range_type: str, field: Column) -> Callable:
    if range_type == "gt":
        return field.__gt__
    if range_type == "gte":
        return field.__ge__
    if range_type == "lt":
        return field.__lt__
    if range_type == "lte":
        return field.__le__
    if range_type == "ne":
        return field.__ne__
    raise ValueError(f"{range_type} not a valid range type ({range_operator_list})")


def generic_range_filter(range_type: str, field: Column) -> Callable[[SearchQuery, str], SearchQuery]:
    filter_operator = get_range_filter(range_type, field)
    convert_filter_value = get_filter_value_convert_function(field)

    def use_filter(query: SearchQuery, value: str) -> SearchQuery:
        if val := convert_filter_value(value):
            value = val
        return query.filter(filter_operator(value))

    return use_filter


def generic_range_filters(
    column: Column, column_alias: Optional[str] = None
) -> dict[str, Callable[[SearchQuery, str], SearchQuery]]:
    dict_filters = {}
    for operator in range_operator_list:
        dict_filters[f"{to_camel(column_alias or column.name)}{operator.capitalize()}"] = generic_range_filter(
            operator, column
        )

    return dict_filters

# Copyright 2019-2020 SURF.
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

from collections.abc import Callable, Iterable
from enum import Enum
from typing import TypeVar, Union

import strawberry
from more_itertools import partition
from pydantic import BaseModel
from sqlalchemy import Column, CompoundSelect, Select, func, select
from sqlalchemy.sql import expression

from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.db.database import BaseModel as DbBaseModel
from orchestrator.db.filters import CallableErrorHandler


@strawberry.enum(description="Sort order (ASC or DESC)")
class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"


class Sort(BaseModel):
    field: str
    order: SortOrder


GenericType = TypeVar("GenericType")
QueryType = Union[Select, CompoundSelect]
ValidSortFunctionsByColumnType = dict[str, Callable[[QueryType, SortOrder], QueryType]]


def generic_sorts_validate(
    valid_sort_functions_by_column: ValidSortFunctionsByColumnType,
) -> Callable[[list[Sort]], tuple[Iterable[Sort], Iterable[Sort]]]:
    """Create generic validate sort factory that creates a validate function based on the valid sort dict.

    Args:
        valid_sort_functions_by_column: The sort functions per column

    Returns function that takes sort parameters and returns a list of invalid and valid Sort items.
    """

    def validate_sort_items(sort_by: list[Sort]) -> tuple[Iterable[Sort], Iterable[Sort]]:
        def _is_valid_sort(item: Sort) -> bool:
            return item.field in valid_sort_functions_by_column

        return partition(_is_valid_sort, sort_by)

    return validate_sort_items


def generic_apply_sorting(
    valid_sort_functions_by_column: ValidSortFunctionsByColumnType,
) -> Callable[[QueryType, Iterable[Sort], CallableErrorHandler], QueryType]:
    def _apply_sorting(query: QueryType, sort_by: Iterable[Sort], handle_sort_error: CallableErrorHandler) -> QueryType:
        for item in sort_by:
            sort_fn = valid_sort_functions_by_column[item.field]
            try:
                query = sort_fn(query, item.order)
            except ProblemDetailException as exception:
                handle_sort_error(exception.detail, field=item.field, order=item.order)
            except ValueError as exception:
                handle_sort_error(str(exception), field=item.field, order=item.order)
        return query

    return _apply_sorting


def generic_sort(
    valid_sort_functions_by_column: ValidSortFunctionsByColumnType,
) -> Callable[[QueryType, list[Sort], CallableErrorHandler], QueryType]:
    valid_sort_keys = sorted(valid_sort_functions_by_column.keys())
    _validate_sorts = generic_sorts_validate(valid_sort_functions_by_column)
    _apply_sorting = generic_apply_sorting(valid_sort_functions_by_column)

    def _sort(
        query: QueryType,
        sort_by: list[Sort],
        handle_sort_error: CallableErrorHandler,
    ) -> QueryType:
        invalid_sort_items, valid_sort_items = _validate_sorts(sort_by)
        if invalid_list := [item.field for item in invalid_sort_items]:
            handle_sort_error("Invalid sort arguments", invalid_sorting=invalid_list, valid_sort_keys=valid_sort_keys)

        return _apply_sorting(query, valid_sort_items, handle_sort_error)

    return _sort


def generic_column_sort(field: Column, base_table: type[DbBaseModel]) -> Callable[[QueryType, SortOrder], QueryType]:
    def sort_function(query: QueryType, order: SortOrder) -> QueryType:
        sa_sort = expression.desc if order == SortOrder.DESC else expression.asc
        sa_order_by = sa_sort(func.lower(field)) if field.type.python_type is str else sa_sort(field)
        select_base = (
            select(query.subquery(base_table.__table__.name))  # type: ignore[attr-defined]
            if isinstance(query, CompoundSelect)
            else query
        )
        return select_base.order_by(sa_order_by)

    return sort_function

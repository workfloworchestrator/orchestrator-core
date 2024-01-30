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

from collections.abc import Callable, Iterable
from typing import Any, Protocol

from more_itertools import partition
from pydantic import BaseModel
from sqlalchemy import Select

from orchestrator.api.error_handling import ProblemDetailException


class CallableErrorHandler(Protocol):
    def __call__(self, message: str, **kwargs: Any) -> None: ...


class Filter(BaseModel):
    field: str
    value: str


QueryType = Select
ValidFilterFunctionsByColumnType = dict[str, Callable[[QueryType, str], QueryType]]


def generic_filters_validate(
    valid_filter_functions_by_column: ValidFilterFunctionsByColumnType,
) -> Callable[[list[Filter]], tuple[Iterable[Filter], Iterable[Filter]]]:
    def _validate_filters(filter_by: list[Filter]) -> tuple[Iterable[Filter], Iterable[Filter]]:
        def _is_valid_filter(item: Filter) -> bool:
            return item.field in valid_filter_functions_by_column and item.value is not None

        return partition(_is_valid_filter, filter_by)

    return _validate_filters


def generic_apply_filters(
    valid_filter_functions_by_column: ValidFilterFunctionsByColumnType,
) -> Callable[[QueryType, Iterable[Filter], CallableErrorHandler], QueryType]:
    def _apply_filters(
        query: QueryType, filter_by: Iterable[Filter], handle_filter_error: CallableErrorHandler
    ) -> QueryType:
        for item in filter_by:
            filter_fn = valid_filter_functions_by_column[item.field]
            try:
                query = filter_fn(query, item.value)
            except ProblemDetailException as exception:
                handle_filter_error(exception.detail, field=item.field, value=item.value)
            except ValueError as exception:
                handle_filter_error(str(exception), field=item.field, value=item.value)
        return query

    return _apply_filters


def generic_filter(
    valid_filter_functions_by_column: ValidFilterFunctionsByColumnType,
) -> Callable[[QueryType, list[Filter], CallableErrorHandler], QueryType]:
    valid_filter_keys = sorted(valid_filter_functions_by_column.keys())
    _validate_filters = generic_filters_validate(valid_filter_functions_by_column)
    _apply_filters = generic_apply_filters(valid_filter_functions_by_column)

    def _filter(
        query: QueryType,
        filter_by: list[Filter],
        handle_filter_error: CallableErrorHandler,
    ) -> QueryType:
        invalid_filter_items, valid_filter_items = _validate_filters(filter_by)
        if invalid_list := [item.field for item in invalid_filter_items]:
            handle_filter_error(
                "Invalid filter arguments", invalid_filters=invalid_list, valid_filter_keys=valid_filter_keys
            )

        return _apply_filters(query, valid_filter_items, handle_filter_error)

    return _filter

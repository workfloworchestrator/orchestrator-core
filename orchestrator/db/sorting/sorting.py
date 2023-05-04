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

from enum import Enum
from typing import Callable, Iterator, TypeVar

from more_itertools import partition
from pydantic import BaseModel
from sqlalchemy.sql import expression

from orchestrator.db.database import BaseModel as SqlBaseModel
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters import CallableErrorHander


class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"


class Sort(BaseModel):
    field: str
    order: SortOrder

    class Config:
        use_enum_values = True


GenericType = TypeVar("GenericType")
QueryType = SearchQuery


def generic_sorts_validate(
    valid_sort_dict: dict[str, str]
) -> Callable[[list[Sort]], tuple[Iterator[Sort], Iterator[Sort]]]:
    """Create generic validate sort factory that creates a validate function based on the valid sort dict.

    Args:
        - valid_sort_dict: dict of column names by valid sort keys
            - key: sort key.
            - value: column name.

    Returns function that takes sort parameters and returns a list of invalid and valid Sort items.
    """

    def validate_sort_items(sort_by: list[Sort]) -> tuple[Iterator[Sort], Iterator[Sort]]:
        return partition(lambda item: item.field in valid_sort_dict, sort_by)

    return validate_sort_items


def generic_apply_sorts(
    valid_sort_dict: dict[str, str], model: SqlBaseModel
) -> Callable[[QueryType, Iterator[Sort]], QueryType]:
    def _apply_sorts(query: QueryType, sort_by: Iterator[Sort]) -> QueryType:
        for item in sort_by:
            field = item.field.lower()
            sort_key = valid_sort_dict[field]

            if item.order == SortOrder.DESC.value:  # type: ignore
                query = query.order_by(expression.desc(model.__dict__[sort_key]))
            else:
                query = query.order_by(expression.asc(model.__dict__[sort_key]))
        return query

    return _apply_sorts


def generic_sort(
    valid_sort_dict: dict[str, str],
    model: SqlBaseModel,
) -> Callable[[QueryType, list[Sort], CallableErrorHander], QueryType]:
    valid_sort_keys = list(valid_sort_dict.keys())
    _validate_sorts = generic_sorts_validate(valid_sort_dict)
    _apply_sorts = generic_apply_sorts(valid_sort_dict, model)

    def _sort(
        query: QueryType,
        sort_by: list[Sort],
        handle_sort_error: CallableErrorHander,
    ) -> QueryType:
        if sort_by:
            invalid_sort_items, valid_sort_items = _validate_sorts(sort_by)
            if invalid_list := [item.dict() for item in invalid_sort_items]:
                handle_sort_error(
                    "Invalid sort arguments",
                    invalid_filters=invalid_list,
                    valid_filter_keys=valid_sort_keys,
                )

            query = _apply_sorts(query, valid_sort_items)
        return query

    return _sort

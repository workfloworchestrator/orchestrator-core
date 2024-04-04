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
import re
from collections.abc import Callable, Iterable
from functools import cache
from typing import Any, Protocol

from more_itertools import partition
from pydantic import BaseModel
from sqlalchemy import Select, false

from orchestrator.utils.helpers import camel_to_snake, to_camel
from orchestrator.utils.search_query import Node, SQLAlchemyVisitor, WhereCondGenerator


class CallableErrorHandler(Protocol):
    def __call__(self, message: str, **kwargs: Any) -> None: ...


class Filter(BaseModel):
    field: str
    value: str


QueryType = Select
ValidFilterFunctionsByColumnType = dict[str, Callable[[QueryType, str], QueryType]]
ColumnMappings = dict[str, WhereCondGenerator]


def generic_filters_validate(
    valid_columns: Iterable[str],
) -> Callable[[list[Filter]], tuple[Iterable[Filter], Iterable[Filter]]]:
    def _validate_filters(filter_by: list[Filter]) -> tuple[Iterable[Filter], Iterable[Filter]]:
        def _is_valid_filter(item: Filter) -> bool:
            return camel_to_snake(item.field) in valid_columns and item.value is not None

        return partition(_is_valid_filter, filter_by)

    return _validate_filters


_re_split = re.compile("[-|]")


def _filter_to_node(filter_item: Filter) -> Node:
    value = filter_item.value
    if value and value[0] == "!":
        updated_filter_item = Filter(field=filter_item.field, value=value[1:])
        return "Negation", _filter_to_node(updated_filter_item)

    # Workaround to deal with date and id fields. These should not be split by '-' like other fields.
    # Fix after deprecating '-' as split-separator in favor of '|'
    should_split = "date" not in filter_item.field.lower() and not filter_item.field.lower().endswith("id")
    values = _re_split.split(filter_item.value) if should_split else filter_item.value.split("|")
    key_node = "Word", filter_item.field
    value_node: Node
    if len(values) > 1:
        value_node = "ValueGroup", [("Word", v) for v in values if v]
    else:
        value_node = "Word", value

    if len(value_node[1]) == 0:
        raise Exception("Invalid filter arguments")

    return "KVTerm", (key_node, value_node)


def _filters_to_and_expr(filter_by: Iterable[Filter]) -> Node:
    return "AndExpression", [_filter_to_node(item) for item in filter_by]


def _apply_filters_fn(
    column_mappings: ColumnMappings,
) -> Callable[[QueryType, Iterable[Filter], CallableErrorHandler], QueryType]:
    def _apply_filters(
        stmt: QueryType, filter_by: Iterable[Filter], handle_filter_error: CallableErrorHandler
    ) -> QueryType:
        try:
            node = _filters_to_and_expr(filter_by)
            visitor = SQLAlchemyVisitor(stmt, column_mappings)
            stmt = visitor.visit_and_expression(stmt, node)
        except ValueError as exception:
            handle_filter_error(str(exception))
        return stmt

    return _apply_filters


def generic_filter_from_clauses(
    column_mappings: ColumnMappings,
) -> Callable[[QueryType, list[Filter], CallableErrorHandler], QueryType]:
    _validate_filters = generic_filters_validate(column_mappings.keys())
    _apply_filters = _apply_filters_fn(column_mappings)

    def _filter(
        query: QueryType,
        filter_by: list[Filter],
        handle_filter_error: CallableErrorHandler,
    ) -> QueryType:
        try:
            invalid_filter_items, valid_filter_items = _validate_filters(filter_by)
            if invalid_list := [item.field for item in invalid_filter_items]:
                valid_filter_keys = sorted([to_camel(k) for k in column_mappings.keys()])
                handle_filter_error(
                    "Invalid filter arguments", invalid_filters=invalid_list, valid_filter_keys=valid_filter_keys
                )

            return _apply_filters(query, valid_filter_items, handle_filter_error)
        except Exception as e:
            handle_filter_error(str(e))
            return query.where(false())

    return _filter


def create_memoized_field_list(column_mappings: dict[str, Any]) -> Callable[[], list[str]]:
    """Used to evaluate the list of keys for filtering/sorting once on first invocation.

    This is necessary to get the fully initialized list values, which can be updated during module importing.
    It works because Python closures are late-binding.
    """

    @cache
    def _filter_fields() -> list[str]:
        return sorted(column_mappings.keys())

    return _filter_fields

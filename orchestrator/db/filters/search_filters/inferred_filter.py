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
import uuid
from datetime import datetime
from typing import Any, Callable

import pytz
import sqlalchemy
from dateutil.parser import parse
from sqlalchemy import BinaryExpression, Cast, ColumnClause, ColumnElement, String, cast
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.sql.operators import eq

from orchestrator.settings import app_settings
from orchestrator.utils.search_query import Node, WhereCondGenerator


def convert_to_datetime(value: str) -> datetime:
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


def _phrase_to_ilike_str(phrase_node: Node) -> str:
    def to_str(node: Node) -> str:
        node_type, value = node
        return f"{value}%" if node_type == "PrefixWord" else f"{value}"

    return " ".join(to_str(w) for w in phrase_node[1])


def _coalesce_if_nullable(field: ColumnElement, default_value: Any = "") -> ColumnElement:
    if isinstance(field, Cast):
        is_nullable = field.wrapped_column_expression.nullable
    else:
        is_nullable = getattr(field, "nullable", False)
    return coalesce(field, default_value) if is_nullable else field


def _filter_string(field: ColumnElement) -> WhereCondGenerator:
    field = _coalesce_if_nullable(field)

    def _clause_gen(node: Node) -> BinaryExpression:
        if node[0] == "Phrase":
            return field.ilike(_phrase_to_ilike_str(node))
        if node[0] == "ValueGroup":
            vals = [w[1] for w in node[1] if w[0] in ["Word", "PrefixWord"]]  # Only works for (Prefix)Words atm
            return field.in_(vals)
        return field.ilike(f"{node[1]}") if app_settings.FILTER_BY_MODE == "exact" else field.ilike(f"%{node[1]}%")

    return _clause_gen


def _filter_as_string(field: ColumnClause) -> WhereCondGenerator:
    return _filter_string(cast(field, String))


RANGE_TYPES = {
    ">": ColumnClause.__gt__,
    ">=": ColumnClause.__ge__,
    "<": ColumnClause.__lt__,
    "<=": ColumnClause.__le__,
    "!": ColumnClause.__ne__,
}


def _filter_comparable(field: ColumnClause, value_converter: Callable[[str], Any]) -> WhereCondGenerator:
    _default_clause = _filter_as_string(field)

    def _clause_gen(node: Node) -> ColumnElement[bool]:
        v = node_to_str_val(node)
        range_comparison_op = next((op for op in [">=", "<=", ">", "<"] if v.startswith(op)), "")
        if range_comparison_op:
            op = RANGE_TYPES.get(range_comparison_op)
            return op(field, value_converter(v[len(range_comparison_op) :]))  # type:ignore
        return _default_clause(node)

    return _clause_gen


def _value_as_bool(v: str) -> bool | None:
    lower = v.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return None


def _filter_bool(field: ColumnClause) -> WhereCondGenerator:
    def _clause_gen(node: Node) -> BinaryExpression | ColumnElement[bool]:
        if node[0] in ["Phrase", "ValueGroup"]:
            vals = [
                boolean_val for w in node[1] if (boolean_val := _value_as_bool(w[1]))
            ]  # Only works for (Prefix)Words atm
            return field.in_(vals)
        boolean_val = _value_as_bool(node[1])
        return eq(field, boolean_val) if boolean_val is not None else sqlalchemy.false()

    return _clause_gen


def inferred_filter(field: ColumnClause) -> WhereCondGenerator:
    python_type = field.type.python_type
    if python_type is str:
        return _filter_string(field)
    if python_type is uuid.UUID:
        return _filter_as_string(field)
    if python_type is bool:
        return _filter_bool(field)
    if python_type is datetime:
        return _filter_comparable(field, convert_to_datetime)
    if python_type is int:
        return _filter_comparable(field, convert_to_int)

    raise Exception(f"Unsupported column type for generic filter: {field}")


def node_to_str_val(node: Node, *, sep: str = " ") -> str:
    if node[0] in ["Phrase", "ValueGroup"]:
        return sep.join(w[1] for w in node[1])
    return node[1]


def filter_exact(field: ColumnClause) -> WhereCondGenerator:
    def _clause_gen(node: Node) -> BinaryExpression[bool] | ColumnElement[bool]:
        if node[0] == "Word":
            return field.ilike(f"{node[1]}")
        if node[0] == "PrefixWord":
            return field.ilike(f"{node[1]}%")
        return _filter_string(field)(node)

    return _clause_gen


def filter_uuid_exact(field: ColumnClause) -> WhereCondGenerator:
    assert field.type.python_type == uuid.UUID  # noqa: S101

    def _clause_gen(node: Node) -> BinaryExpression[bool] | ColumnElement[bool]:
        try:
            v = uuid.UUID(node_to_str_val(node))
        except ValueError:
            # Not a valid uuid
            return sqlalchemy.false()
        return eq(field, v)

    return _clause_gen

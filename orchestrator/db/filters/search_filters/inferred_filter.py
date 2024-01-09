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
from typing import Callable

from sqlalchemy import BinaryExpression, Cast, ColumnClause, ColumnElement, String, cast
from sqlalchemy.sql.functions import coalesce

from orchestrator.utils.search_query import Node


def _phrase_to_ilike_str(phrase_node: Node) -> str:
    def to_str(node: Node) -> str:
        node_type, value = node
        return f"{value}%" if node_type == "PrefixWord" else f"{value}"

    return " ".join(to_str(w) for w in phrase_node[1])


def _coalesce_if_nullable(field: ColumnElement) -> ColumnElement:
    if isinstance(field, Cast):
        is_nullable = field.wrapped_column_expression.nullable
    else:
        is_nullable = getattr(field, "nullable", False)
    return coalesce(field, "") if is_nullable else field  # type:ignore


def _filter_string(field: ColumnElement) -> Callable[[Node], BinaryExpression]:
    field = _coalesce_if_nullable(field)

    def _clause_gen(node: Node) -> BinaryExpression:
        if node[0] == "Phrase":
            return field.ilike(_phrase_to_ilike_str(node))
        if node[0] == "ValueGroup":
            vals = [w[1] for w in node[1] if w in ["Word", "PrefixWord"]]  # Only works for (Prefix)Words atm
            return field.in_(vals)
        return field.ilike(f"%{node[1]}%")

    return _clause_gen


def _filter_as_string(field: ColumnClause) -> Callable[[Node], BinaryExpression]:
    return _filter_string(cast(field, String))


def _value_as_bool(v: str) -> bool:
    return v.lower() in ("yes", "y", "true", "1")


def _filter_bool(field: ColumnClause) -> Callable[[Node], BinaryExpression]:
    def _clause_gen(node: Node) -> BinaryExpression:
        if node[0] in ["Phrase", "ValueGroup"]:
            vals = [_value_as_bool(w[1]) for w in node[1]]  # Only works for (Prefix)Words atm
            return field.in_(vals)
        return field.is_(_value_as_bool(node[1]))

    return _clause_gen


def inferred_filter(field: ColumnClause) -> Callable[[Node], BinaryExpression]:
    python_type = field.type.python_type
    if python_type == str:
        return _filter_string(field)
    if python_type == uuid.UUID:
        return _filter_as_string(field)
    if python_type == bool:
        return _filter_bool(field)
    if python_type == datetime:
        return _filter_as_string(field)

    raise Exception(f"Unsupported column type for generic filter: {field}")


def node_to_str_val(node: Node) -> str:
    if node[0] in ["Phrase", "ValueGroup"]:
        return " ".join(w[1] for w in node[1])
    return node[1]

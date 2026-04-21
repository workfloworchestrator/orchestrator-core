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

"""Tests for inferred_filter: type-based dispatch (str/uuid/bool/datetime/int), convert_to_datetime/int parsing, node_to_str_val, filter_exact (Word/PrefixWord/ValueGroup), and filter_uuid_exact."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
import sqlalchemy
from sqlalchemy import Column, MetaData, Table

from orchestrator.core.db.filters.search_filters.inferred_filter import (
    convert_to_datetime,
    convert_to_int,
    filter_exact,
    filter_uuid_exact,
    inferred_filter,
    node_to_str_val,
)


def _make_table_column(col_name, col_type, nullable=False):
    metadata = MetaData()
    tbl = Table("test_tbl", metadata, Column(col_name, col_type, nullable=nullable))
    return tbl.c[col_name]


# --- convert_to_datetime ---


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("2022-07-21T03:40:48+00:00", id="iso-with-tz"),
        pytest.param("2022-07-21", id="date-only"),
        pytest.param("2022-07-21T03:40:48Z", id="utc-z"),
    ],
)
def test_convert_to_datetime_valid(value: str) -> None:
    result = convert_to_datetime(value)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


@pytest.mark.parametrize(
    "value",
    [pytest.param("not-a-date", id="text"), pytest.param("hello", id="word")],
)
def test_convert_to_datetime_invalid(value: str) -> None:
    with pytest.raises(ValueError, match="is not a valid date"):
        convert_to_datetime(value)


# --- convert_to_int ---


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("0", 0, id="zero"),
        pytest.param("42", 42, id="positive"),
        pytest.param("-7", -7, id="negative"),
    ],
)
def test_convert_to_int_valid(value: str, expected: int) -> None:
    assert convert_to_int(value) == expected


@pytest.mark.parametrize(
    "value",
    [pytest.param("abc", id="alpha"), pytest.param("3.14", id="float"), pytest.param("", id="empty")],
)
def test_convert_to_int_invalid(value: str) -> None:
    with pytest.raises(ValueError, match="is not a valid integer"):
        convert_to_int(value)


# --- node_to_str_val ---


@pytest.mark.parametrize(
    "node,expected",
    [
        pytest.param(("Word", "hello"), "hello", id="word"),
        pytest.param(("PrefixWord", "hel"), "hel", id="prefix"),
        pytest.param(("Phrase", [("Word", "hello"), ("Word", "world")]), "hello world", id="phrase"),
        pytest.param(("ValueGroup", [("Word", "a"), ("Word", "b")]), "a b", id="value-group"),
    ],
)
def test_node_to_str_val(node: tuple, expected: str) -> None:
    assert node_to_str_val(node) == expected


def test_node_to_str_val_custom_separator() -> None:
    assert node_to_str_val(("Phrase", [("Word", "foo"), ("Word", "bar")]), sep="-") == "foo-bar"


# --- inferred_filter dispatch ---


@pytest.mark.parametrize(
    "col_type",
    [
        pytest.param(sqlalchemy.String, id="str"),
        pytest.param(sqlalchemy.Uuid, id="uuid"),
        pytest.param(sqlalchemy.Boolean, id="bool"),
        pytest.param(sqlalchemy.DateTime, id="datetime"),
        pytest.param(sqlalchemy.Integer, id="int"),
    ],
)
def test_inferred_filter_dispatch(col_type: type) -> None:
    col = _make_table_column("test_col", col_type)
    assert callable(inferred_filter(col))


def test_inferred_filter_unsupported_raises() -> None:
    col = MagicMock()
    col.type.python_type = list
    col.nullable = False
    with pytest.raises(Exception, match="Unsupported column type"):
        inferred_filter(col)


def test_bool_filter_invalid_returns_false() -> None:
    col = _make_table_column("active", sqlalchemy.Boolean)
    clause = inferred_filter(col)(("Word", "not-a-bool"))
    assert str(clause) == str(sqlalchemy.false())


def test_int_filter_range_operator() -> None:
    col = _make_table_column("count", sqlalchemy.Integer)
    clause = inferred_filter(col)(("Word", ">5"))
    assert clause is not None


# --- filter_exact ---


def test_filter_exact_prefix_word_uses_like() -> None:
    col = _make_table_column("status", sqlalchemy.String)
    clause = filter_exact(col)(("PrefixWord", "act"))
    assert "LIKE" in str(clause).upper()


# --- filter_uuid_exact ---


def test_filter_uuid_exact_valid() -> None:
    col = _make_table_column("sub_id", sqlalchemy.Uuid)
    clause = filter_uuid_exact(col)(("Word", str(uuid.uuid4())))
    assert str(sqlalchemy.false()) not in str(clause)


def test_filter_uuid_exact_invalid_returns_false() -> None:
    col = _make_table_column("sub_id", sqlalchemy.Uuid)
    clause = filter_uuid_exact(col)(("Word", "not-a-uuid"))
    assert str(clause) == str(sqlalchemy.false())


def test_filter_uuid_exact_non_uuid_column_raises() -> None:
    col = _make_table_column("name", sqlalchemy.String)
    with pytest.raises(AssertionError):
        filter_uuid_exact(col)

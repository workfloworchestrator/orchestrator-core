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
from unittest.mock import MagicMock

import pytest
import sqlalchemy

from orchestrator.db.filters.search_filters.inferred_filter import (
    convert_to_datetime,
    convert_to_int,
    filter_exact,
    filter_uuid_exact,
    inferred_filter,
    node_to_str_val,
)


class TestConvertToDatetime:
    @pytest.mark.parametrize(
        "value",
        [
            "2022-07-21T03:40:48+00:00",
            "2022-07-21",
            "2023-01-01T00:00:00",
            "2022-07-21T03:40:48Z",
        ],
        ids=["iso_with_tz", "date_only", "datetime_no_tz", "utc_z"],
    )
    def test_valid_dates(self, value):
        result = convert_to_datetime(value)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    @pytest.mark.parametrize(
        "value",
        [
            "not-a-date",
            "hello",
        ],
        ids=["text", "word"],
    )
    def test_invalid_dates_raise_value_error(self, value):
        with pytest.raises(ValueError, match="is not a valid date"):
            convert_to_datetime(value)


class TestConvertToInt:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("0", 0),
            ("42", 42),
            ("-7", -7),
            ("1000000", 1000000),
        ],
        ids=["zero", "positive", "negative", "large"],
    )
    def test_valid_ints(self, value, expected):
        assert convert_to_int(value) == expected

    @pytest.mark.parametrize(
        "value",
        ["abc", "3.14", "", "1e5"],
        ids=["alpha", "float", "empty", "scientific"],
    )
    def test_invalid_ints_raise_value_error(self, value):
        with pytest.raises(ValueError, match="is not a valid integer"):
            convert_to_int(value)


class TestNodeToStrVal:
    @pytest.mark.parametrize(
        "node, expected",
        [
            (("Word", "hello"), "hello"),
            (("PrefixWord", "hel"), "hel"),
            (("Phrase", [("Word", "hello"), ("Word", "world")]), "hello world"),
            (("ValueGroup", [("Word", "a"), ("Word", "b")]), "a b"),
            (("Phrase", [("Word", "one")]), "one"),
        ],
        ids=["word", "prefix_word", "phrase", "value_group", "single_phrase"],
    )
    def test_node_to_str_val(self, node, expected):
        assert node_to_str_val(node) == expected

    def test_custom_separator(self):
        node = ("Phrase", [("Word", "foo"), ("Word", "bar")])
        assert node_to_str_val(node, sep="-") == "foo-bar"

    def test_value_group_custom_sep(self):
        node = ("ValueGroup", [("Word", "x"), ("Word", "y")])
        assert node_to_str_val(node, sep=",") == "x,y"


def _make_column(python_type, nullable=False):
    """Create a mock SQLAlchemy column with a given python_type."""
    col = MagicMock()
    col.type.python_type = python_type
    col.nullable = nullable
    return col


def _make_table_column(col_name, col_type, nullable=False):
    """Create a real SQLAlchemy Column bound to a Table so it has proper nullable support."""
    from sqlalchemy import Column, MetaData, Table

    metadata = MetaData()
    tbl = Table("test_tbl", metadata, Column(col_name, col_type, nullable=nullable))
    return tbl.c[col_name]


class TestInferredFilter:
    def test_dispatch_str(self):
        col = _make_table_column("name", sqlalchemy.String)
        filter_fn = inferred_filter(col)
        assert callable(filter_fn)

    def test_dispatch_uuid(self):
        col = _make_table_column("subscription_id", sqlalchemy.Uuid)
        filter_fn = inferred_filter(col)
        assert callable(filter_fn)

    def test_dispatch_bool(self):
        col = _make_table_column("active", sqlalchemy.Boolean)
        filter_fn = inferred_filter(col)
        assert callable(filter_fn)

    def test_dispatch_datetime(self):
        col = _make_table_column("start_date", sqlalchemy.DateTime)
        filter_fn = inferred_filter(col)
        assert callable(filter_fn)

    def test_dispatch_int(self):
        col = _make_table_column("count", sqlalchemy.Integer)
        filter_fn = inferred_filter(col)
        assert callable(filter_fn)

    def test_unsupported_type_raises(self):
        col = _make_column(list)
        with pytest.raises(Exception, match="Unsupported column type"):
            inferred_filter(col)

    def test_str_filter_produces_clause(self):
        col = _make_table_column("name", sqlalchemy.String)
        filter_fn = inferred_filter(col)
        clause = filter_fn(("Word", "hello"))
        assert clause is not None

    def test_bool_filter_true(self):
        col = _make_table_column("active", sqlalchemy.Boolean)
        filter_fn = inferred_filter(col)
        clause = filter_fn(("Word", "true"))
        assert clause is not None

    def test_bool_filter_false(self):
        col = _make_table_column("active", sqlalchemy.Boolean)
        filter_fn = inferred_filter(col)
        clause = filter_fn(("Word", "false"))
        assert clause is not None

    def test_bool_filter_invalid_returns_false(self):
        col = _make_table_column("active", sqlalchemy.Boolean)
        filter_fn = inferred_filter(col)
        clause = filter_fn(("Word", "not-a-bool"))
        # Invalid bool values should produce sqlalchemy.false()
        assert str(clause) == str(sqlalchemy.false())

    def test_int_filter_range_gt(self):
        col = _make_table_column("count", sqlalchemy.Integer)
        filter_fn = inferred_filter(col)
        clause = filter_fn(("Word", ">5"))
        assert clause is not None

    def test_int_filter_range_lte(self):
        col = _make_table_column("count", sqlalchemy.Integer)
        filter_fn = inferred_filter(col)
        clause = filter_fn(("Word", "<=100"))
        assert clause is not None

    def test_int_filter_invalid_raises(self):
        col = _make_table_column("count", sqlalchemy.Integer)
        filter_fn = inferred_filter(col)
        with pytest.raises(ValueError, match="is not a valid integer"):
            filter_fn(("Word", ">notanint"))


class TestFilterExact:
    def test_word_node(self):
        col = _make_table_column("status", sqlalchemy.String)
        filter_fn = filter_exact(col)
        clause = filter_fn(("Word", "active"))
        assert clause is not None

    def test_prefix_word_node(self):
        col = _make_table_column("status", sqlalchemy.String)
        filter_fn = filter_exact(col)
        clause = filter_fn(("PrefixWord", "act"))
        # PrefixWord produces an ilike clause (% suffix is in the bind parameter)
        assert clause is not None
        assert "LIKE" in str(clause).upper()

    def test_value_group_node(self):
        col = _make_table_column("status", sqlalchemy.String)
        filter_fn = filter_exact(col)
        clause = filter_fn(("ValueGroup", [("Word", "a"), ("Word", "b")]))
        assert clause is not None


class TestFilterUuidExact:
    def _make_uuid_column(self):
        return _make_table_column("subscription_id", sqlalchemy.Uuid)

    def test_valid_uuid_produces_clause(self):
        col = self._make_uuid_column()
        filter_fn = filter_uuid_exact(col)
        test_uuid = str(uuid.uuid4())
        clause = filter_fn(("Word", test_uuid))
        assert clause is not None
        assert str(sqlalchemy.false()) not in str(clause)

    def test_invalid_uuid_produces_false(self):
        col = self._make_uuid_column()
        filter_fn = filter_uuid_exact(col)
        clause = filter_fn(("Word", "not-a-uuid"))
        assert str(clause) == str(sqlalchemy.false())

    def test_empty_string_produces_false(self):
        col = self._make_uuid_column()
        filter_fn = filter_uuid_exact(col)
        clause = filter_fn(("Word", ""))
        assert str(clause) == str(sqlalchemy.false())

    def test_phrase_node_valid_uuid(self):
        col = self._make_uuid_column()
        filter_fn = filter_uuid_exact(col)
        test_uuid = str(uuid.uuid4())
        # Phrase node with single word
        clause = filter_fn(("Phrase", [("Word", test_uuid)]))
        assert clause is not None
        assert str(sqlalchemy.false()) not in str(clause)

    def test_non_uuid_column_raises_assertion(self):
        col = _make_table_column("name", sqlalchemy.String)
        with pytest.raises(AssertionError):
            filter_uuid_exact(col)

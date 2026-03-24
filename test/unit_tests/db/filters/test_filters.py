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

"""Tests for filter parsing: _filter_to_node (value splitting, negation, date/ID handling), _filters_to_and_expr, generic_filters_validate (field partitioning), generic_filter_from_clauses (SQL application), and create_memoized_field_list."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import column, select, table

from orchestrator.db.filters.filters import (
    Filter,
    _filter_to_node,
    _filters_to_and_expr,
    create_memoized_field_list,
    generic_filter_from_clauses,
    generic_filters_validate,
)

# --- _filter_to_node ---


@pytest.mark.parametrize(
    "field,value,expected",
    [
        pytest.param(
            "status",
            "active",
            ("KVTerm", (("Word", "status"), ("Word", "active"))),
            id="single-value",
        ),
        pytest.param(
            "tag",
            "foo-bar",
            ("KVTerm", (("Word", "tag"), ("ValueGroup", [("Word", "foo"), ("Word", "bar")]))),
            id="hyphen-split",
        ),
        pytest.param(
            "tag",
            "foo|bar",
            ("KVTerm", (("Word", "tag"), ("ValueGroup", [("Word", "foo"), ("Word", "bar")]))),
            id="pipe-split",
        ),
        pytest.param(
            "startDate",
            "2022-07-21",
            ("KVTerm", (("Word", "startDate"), ("Word", "2022-07-21"))),
            id="date-no-hyphen-split",
        ),
        pytest.param(
            "subscriptionId",
            "abc-def-ghi",
            ("KVTerm", (("Word", "subscriptionId"), ("Word", "abc-def-ghi"))),
            id="id-no-hyphen-split",
        ),
    ],
)
def test_filter_to_node(field: str, value: str, expected: tuple) -> None:
    assert _filter_to_node(Filter(field=field, value=value)) == expected


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("status", "!active", id="negate-single"),
        pytest.param("tag", "!foo-bar", id="negate-group"),
    ],
)
def test_filter_to_node_negation(field: str, value: str) -> None:
    node = _filter_to_node(Filter(field=field, value=value))
    assert node[0] == "Negation"


def test_filter_to_node_double_negation() -> None:
    node = _filter_to_node(Filter(field="status", value="!!active"))
    assert node[0] == "Negation"
    assert node[1][0] == "Negation"


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("tag", "-", id="hyphen-only"),
        pytest.param("startDate", "|", id="pipe-only"),
    ],
)
def test_filter_to_node_empty_group_raises(field: str, value: str) -> None:
    with pytest.raises(Exception, match="Invalid filter arguments"):
        _filter_to_node(Filter(field=field, value=value))


# --- _filters_to_and_expr ---


def test_filters_to_and_expr_combines() -> None:
    filters = [Filter(field="status", value="active"), Filter(field="tag", value="foo")]
    node = _filters_to_and_expr(filters)
    assert node[0] == "AndExpression"
    assert len(node[1]) == 2


def test_filters_to_and_expr_empty() -> None:
    assert _filters_to_and_expr([]) == ("AndExpression", [])


# --- generic_filters_validate ---


def test_filters_validate_partitions() -> None:
    validate = generic_filters_validate(["status", "tag"])
    filters = [
        Filter(field="status", value="active"),
        Filter(field="unknown", value="x"),
        Filter(field="tag", value="foo"),
    ]
    invalid, valid = validate(filters)
    assert [f.field for f in invalid] == ["unknown"]
    assert len(list(valid)) == 2


def test_filters_validate_camel_to_snake() -> None:
    validate = generic_filters_validate(["start_date"])
    invalid, valid = validate([Filter(field="startDate", value="2022-01-01")])
    assert list(invalid) == []
    assert len(list(valid)) == 1


# --- generic_filter_from_clauses ---


def test_filter_from_clauses_invalid_calls_error_handler() -> None:
    error_handler = MagicMock()
    col_fn = MagicMock(return_value=MagicMock())
    filter_fn = generic_filter_from_clauses({"status": col_fn})

    t = table("test", column("status"))
    filter_fn(select(t), [Filter(field="unknownField", value="x")], error_handler)

    error_handler.assert_called_once()
    assert "invalid_filters" in error_handler.call_args.kwargs


# --- create_memoized_field_list ---


def test_memoized_field_list_sorted() -> None:
    fn = create_memoized_field_list({"zebra": MagicMock(), "apple": MagicMock()})
    assert fn() == ["apple", "zebra"]


def test_memoized_field_list_is_cached() -> None:
    fn = create_memoized_field_list({"b": MagicMock(), "a": MagicMock()})
    assert fn() is fn()

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

"""Tests for sorting: generic_sorts_validate (field partitioning), generic_apply_sorting (chaining, error handling), generic_sort (validation+application), and generic_column_sort (SQL compilation)."""

from unittest.mock import MagicMock

import pytest

from orchestrator.db.sorting.sorting import (
    Sort,
    SortOrder,
    generic_apply_sorting,
    generic_column_sort,
    generic_sort,
    generic_sorts_validate,
)

# --- generic_sorts_validate ---


def test_sorts_validate_partitions_valid_and_invalid() -> None:
    sort_fns = {"status": MagicMock(), "tag": MagicMock()}
    validate = generic_sorts_validate(sort_fns)
    sorts = [
        Sort(field="status", order=SortOrder.ASC),
        Sort(field="unknown", order=SortOrder.DESC),
        Sort(field="tag", order=SortOrder.ASC),
    ]
    invalid, valid = validate(sorts)
    invalid_fields = [s.field for s in invalid]
    valid_fields = [s.field for s in valid]
    assert invalid_fields == ["unknown"]
    assert valid_fields == ["status", "tag"]


def test_sorts_validate_empty() -> None:
    validate = generic_sorts_validate({"status": MagicMock()})
    invalid, valid = validate([])
    assert list(invalid) == []
    assert list(valid) == []


# --- generic_apply_sorting ---


def test_apply_sorting_chains_functions() -> None:
    query = MagicMock()
    q2 = MagicMock()
    q3 = MagicMock()
    fn_a = MagicMock(return_value=q2)
    fn_b = MagicMock(return_value=q3)

    apply = generic_apply_sorting({"a": fn_a, "b": fn_b})
    result = apply(query, [Sort(field="a", order=SortOrder.ASC), Sort(field="b", order=SortOrder.DESC)], MagicMock())

    fn_a.assert_called_once_with(query, SortOrder.ASC)
    fn_b.assert_called_once_with(q2, SortOrder.DESC)
    assert result == q3


@pytest.mark.parametrize(
    "exc_type",
    [
        pytest.param(ValueError, id="value-error"),
    ],
)
def test_apply_sorting_error_calls_handler(exc_type: type) -> None:
    query = MagicMock()
    error_handler = MagicMock()
    sort_fn = MagicMock(side_effect=exc_type("bad sort"))

    apply = generic_apply_sorting({"status": sort_fn})
    result = apply(query, [Sort(field="status", order=SortOrder.ASC)], error_handler)

    error_handler.assert_called_once()
    assert result == query


def test_apply_sorting_problem_detail_calls_handler() -> None:
    from orchestrator.api.error_handling import ProblemDetailException

    query = MagicMock()
    error_handler = MagicMock()
    sort_fn = MagicMock(side_effect=ProblemDetailException(status=400, detail="sort failed"))

    apply = generic_apply_sorting({"status": sort_fn})
    result = apply(query, [Sort(field="status", order=SortOrder.ASC)], error_handler)

    error_handler.assert_called_once()
    assert result == query


# --- generic_sort ---


def test_generic_sort_valid_calls_no_error() -> None:
    query = MagicMock()
    sorted_q = MagicMock()
    sort_fn = MagicMock(return_value=sorted_q)
    error_handler = MagicMock()

    sort = generic_sort({"status": sort_fn})
    result = sort(query, [Sort(field="status", order=SortOrder.ASC)], error_handler)

    error_handler.assert_not_called()
    assert result == sorted_q


def test_generic_sort_invalid_reports_valid_keys_sorted() -> None:
    error_handler = MagicMock()
    sort = generic_sort({"zebra": MagicMock(), "apple": MagicMock(), "mango": MagicMock()})
    sort(MagicMock(), [Sort(field="invalid", order=SortOrder.ASC)], error_handler)

    call_kwargs = error_handler.call_args.kwargs
    assert call_kwargs["valid_sort_keys"] == ["apple", "mango", "zebra"]


# --- generic_column_sort ---


@pytest.mark.parametrize(
    "col_type,order,expected_fragment",
    [
        pytest.param("String", SortOrder.ASC, "lower", id="string-asc-uses-lower"),
        pytest.param("String", SortOrder.DESC, "DESC", id="string-desc"),
        pytest.param("Integer", SortOrder.DESC, "DESC", id="integer-desc"),
    ],
)
def test_generic_column_sort_compiles(col_type: str, order: SortOrder, expected_fragment: str) -> None:
    from sqlalchemy import Column, Integer, MetaData, String, Table, select

    type_map = {"String": String, "Integer": Integer}
    metadata = MetaData()
    t = Table("test_table", metadata, Column("my_col", type_map[col_type]))
    col = t.c.my_col

    base_table = MagicMock()
    base_table.__table__ = MagicMock()
    base_table.__table__.name = "test_table"

    sort_fn = generic_column_sort(col, base_table)
    result = sort_fn(select(col), order)
    compiled = str(result.compile())
    assert expected_fragment in compiled or expected_fragment.lower() in compiled.lower()

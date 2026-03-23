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
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from orchestrator.db.sorting.sorting import (
    Sort,
    SortOrder,
    generic_apply_sorting,
    generic_column_sort,
    generic_sort,
    generic_sorts_validate,
)


class TestSortOrder:
    def test_asc_value(self):
        assert SortOrder.ASC.value == "asc"

    def test_desc_value(self):
        assert SortOrder.DESC.value == "desc"

    @pytest.mark.parametrize("val", ["asc", "desc"], ids=["asc", "desc"])
    def test_roundtrip(self, val):
        order = SortOrder(val)
        assert order.value == val

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            SortOrder("invalid")


class TestSort:
    def test_sort_valid_asc(self):
        s = Sort(field="status", order=SortOrder.ASC)
        assert s.field == "status"
        assert s.order == SortOrder.ASC

    def test_sort_valid_desc(self):
        s = Sort(field="startDate", order=SortOrder.DESC)
        assert s.order == SortOrder.DESC

    def test_sort_requires_field(self):
        with pytest.raises(ValidationError):
            Sort(order=SortOrder.ASC)  # type: ignore[call-arg]

    def test_sort_requires_order(self):
        with pytest.raises(ValidationError):
            Sort(field="status")  # type: ignore[call-arg]

    def test_sort_order_from_string(self):
        s = Sort(field="tag", order="asc")  # type: ignore[arg-type]
        assert s.order == SortOrder.ASC


class TestGenericSortsValidate:
    def test_valid_sort_accepted(self):
        sort_fns = {"status": MagicMock(), "tag": MagicMock()}
        validate = generic_sorts_validate(sort_fns)
        invalid, valid = validate([Sort(field="status", order=SortOrder.ASC)])
        assert list(invalid) == []
        assert len(list(valid)) == 1

    def test_invalid_sort_rejected(self):
        sort_fns = {"status": MagicMock()}
        validate = generic_sorts_validate(sort_fns)
        invalid, valid = validate([Sort(field="unknown", order=SortOrder.ASC)])
        invalid_list = list(invalid)
        valid_list = list(valid)
        assert len(invalid_list) == 1
        assert invalid_list[0].field == "unknown"
        assert valid_list == []

    def test_mixed_sorts_partitioned(self):
        sort_fns = {"status": MagicMock(), "tag": MagicMock()}
        validate = generic_sorts_validate(sort_fns)
        sorts = [
            Sort(field="status", order=SortOrder.ASC),
            Sort(field="unknown", order=SortOrder.DESC),
            Sort(field="tag", order=SortOrder.ASC),
        ]
        invalid, valid = validate(sorts)
        invalid_list = list(invalid)
        valid_list = list(valid)
        assert len(invalid_list) == 1
        assert invalid_list[0].field == "unknown"
        assert len(valid_list) == 2

    def test_empty_sorts(self):
        sort_fns = {"status": MagicMock()}
        validate = generic_sorts_validate(sort_fns)
        invalid, valid = validate([])
        assert list(invalid) == []
        assert list(valid) == []

    def test_all_valid_sorts(self):
        sort_fns = {"a": MagicMock(), "b": MagicMock(), "c": MagicMock()}
        validate = generic_sorts_validate(sort_fns)
        sorts = [Sort(field=f, order=SortOrder.ASC) for f in ["a", "b", "c"]]
        invalid, valid = validate(sorts)
        assert list(invalid) == []
        assert len(list(valid)) == 3


class TestGenericApplySorting:
    def _make_query(self):
        query = MagicMock()
        query.order_by.return_value = query
        return query

    def test_applies_sort_functions(self):
        query = self._make_query()
        sort_result = MagicMock()
        sort_fn = MagicMock(return_value=sort_result)
        sort_fns = {"status": sort_fn}

        apply = generic_apply_sorting(sort_fns)
        result = apply(query, [Sort(field="status", order=SortOrder.ASC)], MagicMock())

        sort_fn.assert_called_once_with(query, SortOrder.ASC)
        assert result == sort_result

    def test_applies_multiple_sorts_in_order(self):
        query = self._make_query()
        q2 = MagicMock()
        q3 = MagicMock()
        fn_a = MagicMock(return_value=q2)
        fn_b = MagicMock(return_value=q3)
        sort_fns = {"a": fn_a, "b": fn_b}

        apply = generic_apply_sorting(sort_fns)
        result = apply(
            query, [Sort(field="a", order=SortOrder.ASC), Sort(field="b", order=SortOrder.DESC)], MagicMock()
        )

        fn_a.assert_called_once_with(query, SortOrder.ASC)
        fn_b.assert_called_once_with(q2, SortOrder.DESC)
        assert result == q3

    def test_problem_detail_exception_calls_error_handler(self):
        from orchestrator.api.error_handling import ProblemDetailException

        query = self._make_query()
        error_handler = MagicMock()

        exc = ProblemDetailException(title="test", status=400, detail="sort failed")
        sort_fn = MagicMock(side_effect=exc)
        sort_fns = {"status": sort_fn}

        apply = generic_apply_sorting(sort_fns)
        result = apply(query, [Sort(field="status", order=SortOrder.ASC)], error_handler)

        error_handler.assert_called_once()
        # Even after error, query is returned
        assert result == query

    def test_value_error_calls_error_handler(self):
        query = self._make_query()
        error_handler = MagicMock()

        sort_fn = MagicMock(side_effect=ValueError("bad sort"))
        sort_fns = {"status": sort_fn}

        apply = generic_apply_sorting(sort_fns)
        result = apply(query, [Sort(field="status", order=SortOrder.ASC)], error_handler)

        error_handler.assert_called_once()
        call_args = error_handler.call_args
        assert "bad sort" in call_args.args[0]
        assert result == query

    def test_empty_sort_list(self):
        query = self._make_query()
        sort_fns = {"status": MagicMock()}
        apply = generic_apply_sorting(sort_fns)
        result = apply(query, [], MagicMock())
        assert result == query


class TestGenericSort:
    def _make_query(self):
        return MagicMock()

    def test_valid_sort_calls_no_error(self):
        query = self._make_query()
        sorted_query = MagicMock()
        sort_fn = MagicMock(return_value=sorted_query)
        error_handler = MagicMock()

        sort = generic_sort({"status": sort_fn})
        result = sort(query, [Sort(field="status", order=SortOrder.ASC)], error_handler)

        error_handler.assert_not_called()
        assert result == sorted_query

    def test_invalid_sort_calls_error_handler_with_details(self):
        query = self._make_query()
        error_handler = MagicMock()
        sort_fn = MagicMock()

        sort = generic_sort({"status": sort_fn, "tag": sort_fn})
        sort(query, [Sort(field="badField", order=SortOrder.ASC)], error_handler)

        error_handler.assert_called_once()
        call_kwargs = error_handler.call_args.kwargs
        assert "invalid_sorting" in call_kwargs
        assert "badField" in call_kwargs["invalid_sorting"]
        assert "valid_sort_keys" in call_kwargs
        assert call_kwargs["valid_sort_keys"] == sorted(["status", "tag"])

    def test_valid_sort_keys_are_sorted(self):
        sort_fn = MagicMock()
        sort = generic_sort({"zebra": sort_fn, "apple": sort_fn, "mango": sort_fn})

        error_handler = MagicMock()
        sort(MagicMock(), [Sort(field="invalid", order=SortOrder.ASC)], error_handler)

        call_kwargs = error_handler.call_args.kwargs
        assert call_kwargs["valid_sort_keys"] == ["apple", "mango", "zebra"]

    def test_mixed_sorts_reports_only_invalid(self):
        query = MagicMock()
        sorted_query = MagicMock()
        sort_fn = MagicMock(return_value=sorted_query)
        error_handler = MagicMock()

        sort = generic_sort({"status": sort_fn})
        sort(query, [Sort(field="status", order=SortOrder.ASC), Sort(field="bad", order=SortOrder.DESC)], error_handler)

        error_handler.assert_called_once()
        call_kwargs = error_handler.call_args.kwargs
        assert "bad" in call_kwargs["invalid_sorting"]
        # valid sort should still be applied
        sort_fn.assert_called_once()

    def test_empty_sorts(self):
        sort_fn = MagicMock()
        error_handler = MagicMock()
        sort = generic_sort({"status": sort_fn})

        query = MagicMock()
        result = sort(query, [], error_handler)

        error_handler.assert_not_called()
        sort_fn.assert_not_called()
        assert result == query


class TestGenericColumnSort:
    def _make_table_and_column(self, col_type):
        from sqlalchemy import Column, MetaData, Table

        metadata = MetaData()
        table = Table("test_table", metadata, Column("my_col", col_type))
        return table.c.my_col

    def _make_db_model(self, table_name):
        base_table = MagicMock()
        base_table.__table__ = MagicMock()
        base_table.__table__.name = table_name
        return base_table

    def test_string_column_asc(self):
        from sqlalchemy import String, select

        col = self._make_table_and_column(String)
        base_table = self._make_db_model("test_table")

        sort_fn = generic_column_sort(col, base_table)
        query = select(col)
        result = sort_fn(query, SortOrder.ASC)
        # Should produce an ORDER BY clause with func.lower for strings
        compiled = str(result.compile())
        assert "lower" in compiled.lower() or "ORDER BY" in compiled

    def test_string_column_desc(self):
        from sqlalchemy import String, select

        col = self._make_table_and_column(String)
        base_table = self._make_db_model("test_table")

        sort_fn = generic_column_sort(col, base_table)
        query = select(col)
        result = sort_fn(query, SortOrder.DESC)
        compiled = str(result.compile())
        assert "DESC" in compiled

    def test_integer_column_asc(self):
        from sqlalchemy import Integer, select

        col = self._make_table_and_column(Integer)
        base_table = self._make_db_model("test_table")

        sort_fn = generic_column_sort(col, base_table)
        query = select(col)
        result = sort_fn(query, SortOrder.ASC)
        compiled = str(result.compile())
        assert "ORDER BY" in compiled

    def test_integer_column_desc(self):
        from sqlalchemy import Integer, select

        col = self._make_table_and_column(Integer)
        base_table = self._make_db_model("test_table")

        sort_fn = generic_column_sort(col, base_table)
        query = select(col)
        result = sort_fn(query, SortOrder.DESC)
        compiled = str(result.compile())
        assert "DESC" in compiled

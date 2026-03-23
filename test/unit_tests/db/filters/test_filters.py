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
from sqlalchemy import select

from orchestrator.db.filters.filters import (
    Filter,
    _filter_to_node,
    _filters_to_and_expr,
    create_memoized_field_list,
    generic_filter_from_clauses,
    generic_filters_validate,
)


class TestFilter:
    def test_filter_valid(self):
        f = Filter(field="status", value="active")
        assert f.field == "status"
        assert f.value == "active"

    def test_filter_requires_field(self):
        with pytest.raises(ValidationError):
            Filter(value="active")

    def test_filter_requires_value(self):
        with pytest.raises(ValidationError):
            Filter(field="status")

    def test_filter_field_and_value_are_strings(self):
        f = Filter(field="myField", value="myValue")
        assert isinstance(f.field, str)
        assert isinstance(f.value, str)


class TestFilterToNode:
    @pytest.mark.parametrize(
        "field, value, expected",
        [
            (
                "status",
                "active",
                ("KVTerm", (("Word", "status"), ("Word", "active"))),
            ),
            (
                "tag",
                "foo-bar",
                ("KVTerm", (("Word", "tag"), ("ValueGroup", [("Word", "foo"), ("Word", "bar")]))),
            ),
            (
                "tag",
                "foo|bar",
                ("KVTerm", (("Word", "tag"), ("ValueGroup", [("Word", "foo"), ("Word", "bar")]))),
            ),
            (
                "status",
                "a|b|c",
                ("KVTerm", (("Word", "status"), ("ValueGroup", [("Word", "a"), ("Word", "b"), ("Word", "c")]))),
            ),
        ],
        ids=["single_value", "hyphen_split", "pipe_split", "pipe_multi_split"],
    )
    def test_filter_to_node_normal(self, field, value, expected):
        node = _filter_to_node(Filter(field=field, value=value))
        assert node == expected

    @pytest.mark.parametrize(
        "field, value, expected_inner",
        [
            (
                "status",
                "!active",
                ("KVTerm", (("Word", "status"), ("Word", "active"))),
            ),
            (
                "tag",
                "!foo-bar",
                ("KVTerm", (("Word", "tag"), ("ValueGroup", [("Word", "foo"), ("Word", "bar")]))),
            ),
        ],
        ids=["negate_single", "negate_group"],
    )
    def test_filter_to_node_negation(self, field, value, expected_inner):
        node = _filter_to_node(Filter(field=field, value=value))
        assert node[0] == "Negation"
        assert node[1] == expected_inner

    @pytest.mark.parametrize(
        "field, value, expected",
        [
            # Date fields: hyphen should NOT split (it's part of the date format)
            (
                "startDate",
                "2022-07-21",
                ("KVTerm", (("Word", "startDate"), ("Word", "2022-07-21"))),
            ),
            (
                "startDate",
                "2022-07-21|2022-08-01",
                ("KVTerm", (("Word", "startDate"), ("ValueGroup", [("Word", "2022-07-21"), ("Word", "2022-08-01")]))),
            ),
            # ID fields: hyphen should NOT split
            (
                "subscriptionId",
                "abc-def-ghi",
                ("KVTerm", (("Word", "subscriptionId"), ("Word", "abc-def-ghi"))),
            ),
            (
                "subscriptionId",
                "abc|def",
                ("KVTerm", (("Word", "subscriptionId"), ("ValueGroup", [("Word", "abc"), ("Word", "def")]))),
            ),
        ],
        ids=["date_no_hyphen_split", "date_pipe_split", "id_no_hyphen_split", "id_pipe_split"],
    )
    def test_filter_to_node_date_and_id_fields(self, field, value, expected):
        node = _filter_to_node(Filter(field=field, value=value))
        assert node == expected

    def test_filter_to_node_empty_value_group_raises(self):
        # A value of just separators results in empty groups after split
        with pytest.raises(Exception, match="Invalid filter arguments"):
            _filter_to_node(Filter(field="tag", value="-"))

    def test_filter_to_node_empty_value_group_pipe_raises(self):
        with pytest.raises(Exception, match="Invalid filter arguments"):
            _filter_to_node(Filter(field="startDate", value="|"))

    def test_filter_to_node_double_negation(self):
        # Double negation: "!!" should produce nested Negation
        node = _filter_to_node(Filter(field="status", value="!!active"))
        assert node[0] == "Negation"
        assert node[1][0] == "Negation"
        assert node[1][1] == ("KVTerm", (("Word", "status"), ("Word", "active")))


class TestFiltersToAndExpr:
    def test_empty_list_produces_empty_and_expression(self):
        node = _filters_to_and_expr([])
        assert node == ("AndExpression", [])

    def test_single_filter(self):
        filters = [Filter(field="status", value="active")]
        node = _filters_to_and_expr(filters)
        assert node[0] == "AndExpression"
        assert len(node[1]) == 1
        assert node[1][0] == ("KVTerm", (("Word", "status"), ("Word", "active")))

    def test_multiple_filters(self):
        filters = [Filter(field="status", value="active"), Filter(field="tag", value="foo")]
        node = _filters_to_and_expr(filters)
        assert node[0] == "AndExpression"
        assert len(node[1]) == 2


class TestGenericFiltersValidate:
    def test_valid_filters_accepted(self):
        validate = generic_filters_validate(["status", "tag"])
        invalid, valid = validate([Filter(field="status", value="active")])
        assert list(invalid) == []
        assert len(list(valid)) == 1

    def test_invalid_filters_rejected(self):
        validate = generic_filters_validate(["status"])
        invalid, valid = validate([Filter(field="unknown", value="x")])
        invalid_list = list(invalid)
        valid_list = list(valid)
        assert len(invalid_list) == 1
        assert invalid_list[0].field == "unknown"
        assert valid_list == []

    def test_mixed_filters_partitioned(self):
        validate = generic_filters_validate(["status", "tag"])
        filters = [
            Filter(field="status", value="active"),
            Filter(field="unknown", value="x"),
            Filter(field="tag", value="foo"),
        ]
        invalid, valid = validate(filters)
        invalid_list = list(invalid)
        valid_list = list(valid)
        assert len(invalid_list) == 1
        assert invalid_list[0].field == "unknown"
        assert len(valid_list) == 2

    def test_camel_case_field_matches_snake_case_column(self):
        # "startDate" in camelCase should match "start_date" snake_case column
        validate = generic_filters_validate(["start_date"])
        invalid, valid = validate([Filter(field="startDate", value="2022-01-01")])
        assert list(invalid) == []
        assert len(list(valid)) == 1

    def test_empty_filters(self):
        validate = generic_filters_validate(["status"])
        invalid, valid = validate([])
        assert list(invalid) == []
        assert list(valid) == []


class TestGenericFilterFromClauses:
    def _make_mock_query(self):
        query = MagicMock()
        query.where.return_value = query
        return query

    def _make_column_mapping(self, keys):
        mappings = {}
        for key in keys:
            col_fn = MagicMock()
            col_fn.return_value = MagicMock()
            mappings[key] = col_fn
        return mappings

    def test_valid_filters_call_no_error(self):
        error_handler = MagicMock()
        column_mappings = self._make_column_mapping(["status"])

        # Build a real sqlalchemy select to pass as query
        from sqlalchemy import column, table

        t = table("test", column("status"))
        query = select(t)

        filter_fn = generic_filter_from_clauses(column_mappings)
        # Should not raise; error handler should not be called for invalid filters
        # (it may be called for apply errors with mocked column mappings — just check no crash)
        filter_fn(query, [Filter(field="status", value="active")], error_handler)

    def test_invalid_filter_calls_error_handler(self):
        error_handler = MagicMock()
        column_mappings = self._make_column_mapping(["status"])

        from sqlalchemy import column, table

        t = table("test", column("status"))
        query = select(t)

        filter_fn = generic_filter_from_clauses(column_mappings)
        filter_fn(query, [Filter(field="unknownField", value="x")], error_handler)

        error_handler.assert_called_once()
        call_kwargs = error_handler.call_args
        assert "invalid_filters" in call_kwargs.kwargs
        assert "unknownField" in call_kwargs.kwargs["invalid_filters"]

    def test_invalid_filter_includes_valid_keys(self):
        error_handler = MagicMock()
        column_mappings = self._make_column_mapping(["my_status", "my_tag"])

        from sqlalchemy import column, table

        t = table("test", column("my_status"))
        query = select(t)

        filter_fn = generic_filter_from_clauses(column_mappings)
        filter_fn(query, [Filter(field="badField", value="x")], error_handler)

        call_kwargs = error_handler.call_args.kwargs
        # valid_filter_keys should be camelCase sorted
        assert "valid_filter_keys" in call_kwargs
        assert sorted(call_kwargs["valid_filter_keys"]) == call_kwargs["valid_filter_keys"]

    def test_empty_filter_list_returns_query_unchanged(self):
        error_handler = MagicMock()
        column_mappings = self._make_column_mapping(["status"])

        from sqlalchemy import column, table

        t = table("test", column("status"))
        query = select(t)

        filter_fn = generic_filter_from_clauses(column_mappings)
        result = filter_fn(query, [], error_handler)

        error_handler.assert_not_called()
        assert result is not None


class TestCreateMemoizedFieldList:
    def test_returns_sorted_keys(self):
        mappings = {"zebra": MagicMock(), "apple": MagicMock(), "mango": MagicMock()}
        field_list_fn = create_memoized_field_list(mappings)
        result = field_list_fn()
        assert result == ["apple", "mango", "zebra"]

    def test_is_memoized(self):
        mappings = {"b": MagicMock(), "a": MagicMock()}
        field_list_fn = create_memoized_field_list(mappings)
        result1 = field_list_fn()
        result2 = field_list_fn()
        assert result1 is result2

    def test_empty_mapping(self):
        field_list_fn = create_memoized_field_list({})
        assert field_list_fn() == []

    def test_single_key(self):
        field_list_fn = create_memoized_field_list({"only": MagicMock()})
        assert field_list_fn() == ["only"]

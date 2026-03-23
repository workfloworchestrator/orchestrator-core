# Copyright 2019-2025 SURF, GÉANT.
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

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from orchestrator.schemas.search_requests import SearchRequest
from orchestrator.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.search.filters import FilterTree, PathFilter
from orchestrator.search.filters.base import EqualityFilter, StringFilter
from orchestrator.search.filters.date_filters import DateRangeFilter, DateValueFilter
from orchestrator.search.filters.elastic_dsl import (
    ElasticQuery,
    elastic_to_filter_tree,
)
from orchestrator.search.filters.ltree_filters import LtreeFilter
from orchestrator.search.filters.numeric_filter import NumericRangeFilter, NumericValueFilter

ElasticQueryAdapter: TypeAdapter[ElasticQuery] = TypeAdapter(ElasticQuery)


def _parse_and_get_leaf(es_dsl: dict[str, Any]) -> PathFilter:
    """Parse ES DSL and return the first leaf as a PathFilter."""
    es = ElasticQueryAdapter.validate_python(es_dsl)
    tree = elastic_to_filter_tree(es)
    leaf = tree.children[0]
    assert isinstance(leaf, PathFilter)
    return leaf


# ---------------------------------------------------------------------------
# term queries
# ---------------------------------------------------------------------------


class TestTermQuery:
    @pytest.mark.parametrize(
        "value, expected_value_kind",
        [
            ("active", UIType.STRING),
            (True, UIType.BOOLEAN),
            (False, UIType.BOOLEAN),
            ("550e8400-e29b-41d4-a716-446655440000", UIType.STRING),
        ],
        ids=["string", "bool-true", "bool-false", "uuid"],
    )
    def test_term_value_kinds(self, value: Any, expected_value_kind: UIType) -> None:
        leaf = _parse_and_get_leaf({"term": {"subscription.field": value}})
        assert isinstance(leaf.condition, EqualityFilter)
        assert leaf.condition.op == FilterOp.EQ
        assert leaf.condition.value == value
        assert leaf.value_kind == expected_value_kind

    def test_term_preserves_path(self) -> None:
        leaf = _parse_and_get_leaf({"term": {"subscription.status": "active"}})
        assert leaf.path == "subscription.status"


# ---------------------------------------------------------------------------
# range queries — single bound
# ---------------------------------------------------------------------------


class TestRangeQuery:
    @pytest.mark.parametrize(
        "es_op, value, expected_filter_type, expected_op, expected_value_kind",
        [
            ("gt", "2025-01-01", DateValueFilter, FilterOp.GT, UIType.DATETIME),
            ("gte", "2025-06-15", DateValueFilter, FilterOp.GTE, UIType.DATETIME),
            ("lt", "2025-12-31", DateValueFilter, FilterOp.LT, UIType.DATETIME),
            ("lte", "2025-03-01", DateValueFilter, FilterOp.LTE, UIType.DATETIME),
            ("gt", 100, NumericValueFilter, FilterOp.GT, UIType.NUMBER),
            ("gte", 0, NumericValueFilter, FilterOp.GTE, UIType.NUMBER),
            ("lt", 9999, NumericValueFilter, FilterOp.LT, UIType.NUMBER),
            ("lte", 1000, NumericValueFilter, FilterOp.LTE, UIType.NUMBER),
        ],
        ids=["date-gt", "date-gte", "date-lt", "date-lte", "num-gt", "num-gte", "num-lt", "num-lte"],
    )
    def test_range_single_bound(
        self,
        es_op: str,
        value: Any,
        expected_filter_type: type,
        expected_op: FilterOp,
        expected_value_kind: UIType,
    ) -> None:
        leaf = _parse_and_get_leaf({"range": {"field": {es_op: value}}})
        assert isinstance(leaf.condition, expected_filter_type)
        assert leaf.condition.op == expected_op
        assert leaf.condition.value == value
        assert leaf.value_kind == expected_value_kind

    @pytest.mark.parametrize(
        "start, end, expected_filter_type, expected_value_kind",
        [
            ("2025-01-01", "2025-12-31", DateRangeFilter, UIType.DATETIME),
            (100, 10000, NumericRangeFilter, UIType.NUMBER),
        ],
        ids=["date-between", "numeric-between"],
    )
    def test_range_between(self, start: Any, end: Any, expected_filter_type: type, expected_value_kind: UIType) -> None:
        leaf = _parse_and_get_leaf({"range": {"field": {"gte": start, "lte": end}}})
        assert isinstance(leaf.condition, expected_filter_type)
        assert leaf.condition.op == FilterOp.BETWEEN
        assert leaf.condition.value.start == start
        assert leaf.condition.value.end == end
        assert leaf.value_kind == expected_value_kind


# ---------------------------------------------------------------------------
# wildcard queries
# ---------------------------------------------------------------------------


class TestWildcardQuery:
    @pytest.mark.parametrize(
        "es_pattern, expected_sql",
        [
            ("*fiber*", "%fiber%"),
            ("node-?", "node-_"),
            ("prefix*suffix", "prefix%suffix"),
            ("?start", "_start"),
        ],
        ids=["star", "question", "mixed-star", "leading-question"],
    )
    def test_wildcard_pattern_conversion(self, es_pattern: str, expected_sql: str) -> None:
        leaf = _parse_and_get_leaf({"wildcard": {"field": {"value": es_pattern}}})
        assert isinstance(leaf.condition, StringFilter)
        assert leaf.condition.op == FilterOp.LIKE
        assert leaf.condition.value == expected_sql
        assert leaf.value_kind == UIType.STRING


# ---------------------------------------------------------------------------
# exists queries
# ---------------------------------------------------------------------------


class TestExistsQuery:
    def test_exists_to_ltree_filter(self) -> None:
        leaf = _parse_and_get_leaf({"exists": {"field": "node"}})
        assert leaf.path == "*"
        assert isinstance(leaf.condition, LtreeFilter)
        assert leaf.condition.op == FilterOp.ENDS_WITH
        assert leaf.condition.value == "node"
        assert leaf.value_kind == UIType.COMPONENT


# ---------------------------------------------------------------------------
# bool queries
# ---------------------------------------------------------------------------


class TestBoolQuery:
    @pytest.mark.parametrize(
        "clause_key, expected_op",
        [
            ("must", BooleanOperator.AND),
            ("should", BooleanOperator.OR),
        ],
        ids=["must-and", "should-or"],
    )
    def test_bool_clause_to_tree(self, clause_key: str, expected_op: BooleanOperator) -> None:
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    clause_key: [
                        {"term": {"subscription.status": "active"}},
                        {"term": {"subscription.product": "fiber"}},
                    ]
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == expected_op
        assert len(tree.children) == 2

    @pytest.mark.parametrize(
        "es_dsl, expected_type, expected_op",
        [
            (
                {"bool": {"must_not": [{"term": {"subscription.status": "terminated"}}]}},
                EqualityFilter,
                FilterOp.NEQ,
            ),
            (
                {"bool": {"must_not": [{"range": {"subscription.start_date": {"gt": "2025-01-01"}}}]}},
                DateValueFilter,
                FilterOp.LTE,
            ),
        ],
        ids=["term-inverts-to-neq", "range-inverts-op"],
    )
    def test_bool_must_not_single(self, es_dsl: dict[str, Any], expected_type: type, expected_op: FilterOp) -> None:
        leaf = _parse_and_get_leaf(es_dsl)
        assert isinstance(leaf.condition, expected_type)
        assert leaf.condition.op == expected_op

    def test_bool_combined_must_and_must_not(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "must": [{"term": {"subscription.product": "fiber"}}],
                    "must_not": [{"term": {"subscription.status": "terminated"}}],
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.AND
        assert len(tree.children) == 2
        must_leaf = tree.children[0]
        assert isinstance(must_leaf, PathFilter)
        assert must_leaf.condition.value == "fiber"
        not_leaf = tree.children[1]
        assert isinstance(not_leaf, PathFilter)
        assert isinstance(not_leaf.condition, EqualityFilter)
        assert not_leaf.condition.op == FilterOp.NEQ

    def test_nested_bool_queries(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "must": [
                        {"term": {"subscription.status": "active"}},
                        {
                            "bool": {
                                "should": [
                                    {"term": {"subscription.product": "fiber"}},
                                    {"term": {"subscription.product": "wireless"}},
                                ]
                            }
                        },
                    ]
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.AND
        assert len(tree.children) == 2
        nested = tree.children[1]
        assert isinstance(nested, FilterTree)
        assert nested.op == BooleanOperator.OR
        assert len(nested.children) == 2

    def test_bool_must_not_range_between_inverts_to_or(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {"bool": {"must_not": [{"range": {"subscription.bandwidth": {"gte": 100, "lte": 10000}}}]}}
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.OR
        assert len(tree.children) == 2
        assert isinstance(tree.children[0], PathFilter)
        assert isinstance(tree.children[0].condition, NumericValueFilter)
        assert tree.children[0].condition.op == FilterOp.LT
        assert isinstance(tree.children[1], PathFilter)
        assert isinstance(tree.children[1].condition, NumericValueFilter)
        assert tree.children[1].condition.op == FilterOp.GT


# ---------------------------------------------------------------------------
# value kind inference
# ---------------------------------------------------------------------------


class TestValueKindInference:
    @pytest.mark.parametrize(
        "value, expected_kind",
        [
            ("2025-06-15", UIType.DATETIME),
            (42, UIType.NUMBER),
            (3.14, UIType.NUMBER),
            (True, UIType.BOOLEAN),
            ("hello", UIType.STRING),
        ],
        ids=["datetime", "int", "float", "boolean", "string"],
    )
    def test_value_kind_inference(self, value: Any, expected_kind: UIType) -> None:
        leaf = _parse_and_get_leaf({"term": {"field": value}})
        assert leaf.value_kind == expected_kind


# ---------------------------------------------------------------------------
# validation / edge cases
# ---------------------------------------------------------------------------


class TestValidation:
    def test_empty_bool_raises(self) -> None:
        with pytest.raises(ValidationError, match="at least one clause"):
            ElasticQueryAdapter.validate_python({"bool": {}})

    @pytest.mark.parametrize(
        "query_type, payload",
        [
            ("term", {"term": {"a": 1, "b": 2}}),
            ("range", {"range": {"a": {"gt": 1}, "b": {"lt": 2}}}),
            ("wildcard", {"wildcard": {"a": {"value": "*"}, "b": {"value": "?"}}}),
        ],
        ids=["term-multi-field", "range-multi-field", "wildcard-multi-field"],
    )
    def test_multi_field_query_raises(self, query_type: str, payload: dict[str, Any]) -> None:
        with pytest.raises(ValidationError, match="too_long"):
            ElasticQueryAdapter.validate_python(payload)

    def test_range_no_recognised_bounds_raises(self) -> None:
        es = ElasticQueryAdapter.validate_python({"range": {"field": {"unknown_op": 42}}})
        with pytest.raises(ValueError, match="no recognised bounds"):
            elastic_to_filter_tree(es)


# ---------------------------------------------------------------------------
# must_not edge cases
# ---------------------------------------------------------------------------


class TestMustNotEdgeCases:
    def test_must_not_date_between_inverts_to_or(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {"bool": {"must_not": [{"range": {"subscription.start_date": {"gte": "2025-01-01", "lte": "2025-12-31"}}}]}}
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.OR
        assert len(tree.children) == 2
        lo = tree.children[0]
        hi = tree.children[1]
        assert isinstance(lo, PathFilter)
        assert isinstance(lo.condition, DateValueFilter)
        assert lo.condition.op == FilterOp.LT
        assert lo.condition.value == "2025-01-01"
        assert isinstance(hi, PathFilter)
        assert isinstance(hi.condition, DateValueFilter)
        assert hi.condition.op == FilterOp.GT
        assert hi.condition.value == "2025-12-31"

    def test_must_not_wildcard_passes_through(self) -> None:
        """Wildcard filters are non-invertible; must_not passes them through as-is."""
        es = ElasticQueryAdapter.validate_python({"bool": {"must_not": [{"wildcard": {"field": {"value": "*test*"}}}]}})
        tree = elastic_to_filter_tree(es)
        assert len(tree.children) == 1
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, StringFilter)
        assert leaf.condition.op == FilterOp.LIKE

    def test_must_not_nested_bool_passes_through(self) -> None:
        """Complex sub-trees in must_not are passed through as-is."""
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "must_not": [
                        {
                            "bool": {
                                "must": [
                                    {"term": {"a": "x"}},
                                    {"term": {"b": "y"}},
                                ]
                            }
                        }
                    ]
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.AND

    def test_must_not_numeric_value_inverts(self) -> None:
        leaf = _parse_and_get_leaf({"bool": {"must_not": [{"range": {"field": {"gte": 100}}}]}})
        assert isinstance(leaf.condition, NumericValueFilter)
        assert leaf.condition.op == FilterOp.LT


# ---------------------------------------------------------------------------
# bool combination edge cases
# ---------------------------------------------------------------------------


class TestBoolCombinations:
    def test_bool_combined_must_and_should(self) -> None:
        """When both must and should are present, should becomes OR sub-tree under AND."""
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "must": [{"term": {"status": "active"}}],
                    "should": [
                        {"term": {"product": "fiber"}},
                        {"term": {"product": "wireless"}},
                    ],
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.AND
        assert len(tree.children) == 2
        # First child is the must term
        assert isinstance(tree.children[0], PathFilter)
        # Second child is the OR sub-tree from should
        nested = tree.children[1]
        assert isinstance(nested, FilterTree)
        assert nested.op == BooleanOperator.OR
        assert len(nested.children) == 2

    def test_bool_single_should_unwraps(self) -> None:
        """A single should child is unwrapped (no FilterTree wrapper)."""
        es = ElasticQueryAdapter.validate_python({"bool": {"should": [{"term": {"status": "active"}}]}})
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        # elastic_to_filter_tree wraps single PathFilter in AND tree
        assert tree.op == BooleanOperator.AND
        assert len(tree.children) == 1
        assert isinstance(tree.children[0], PathFilter)

    def test_bool_must_not_only_multiple(self) -> None:
        """Multiple must_not clauses are combined under AND."""
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "must_not": [
                        {"term": {"status": "terminated"}},
                        {"term": {"status": "provisioning"}},
                    ]
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.AND
        assert len(tree.children) == 2
        for child in tree.children:
            assert isinstance(child, PathFilter)
            assert isinstance(child.condition, EqualityFilter)
            assert child.condition.op == FilterOp.NEQ

    def test_bool_all_three_clauses(self) -> None:
        """Bool with must, should, and must_not all present."""
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "must": [{"term": {"status": "active"}}],
                    "should": [
                        {"term": {"product": "fiber"}},
                        {"term": {"product": "wireless"}},
                    ],
                    "must_not": [{"term": {"region": "deprecated"}}],
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.AND
        # must term + should OR sub-tree + must_not inverted term = 3 children
        assert len(tree.children) == 3

    def test_range_non_gte_lte_two_bound_uses_first(self) -> None:
        """Range with gt+lt (not gte+lte) falls through to single-bound logic."""
        leaf = _parse_and_get_leaf({"range": {"field": {"gt": 10, "lt": 100}}})
        # Should pick first matching op from _RANGE_OPS iteration order (gt first)
        assert isinstance(leaf.condition, NumericValueFilter)
        assert leaf.condition.op == FilterOp.GT
        assert leaf.condition.value == 10


# ---------------------------------------------------------------------------
# SearchRequest integration
# ---------------------------------------------------------------------------


class TestSearchRequestIntegration:
    @pytest.mark.parametrize(
        "filters, expected_op, expected_children",
        [
            (
                {
                    "bool": {
                        "must": [
                            {"term": {"subscription.status": "active"}},
                            {"range": {"subscription.start_date": {"gte": "2025-01-01"}}},
                        ]
                    }
                },
                BooleanOperator.AND,
                2,
            ),
            (
                {"term": {"subscription.status": "active"}},
                BooleanOperator.AND,
                1,
            ),
        ],
        ids=["es-dsl-bool", "es-dsl-term"],
    )
    def test_search_request_accepts_elastic_dsl(
        self, filters: dict[str, Any], expected_op: BooleanOperator, expected_children: int
    ) -> None:
        request = SearchRequest(filters=filters)  # type: ignore[arg-type]
        assert isinstance(request.filters, FilterTree)
        assert request.filters.op == expected_op
        assert len(request.filters.children) == expected_children

    def test_search_request_accepts_filter_tree(self) -> None:
        request = SearchRequest(
            filters={  # type: ignore[arg-type]
                "op": "AND",
                "children": [
                    {
                        "path": "subscription.status",
                        "condition": {"op": "eq", "value": "active"},
                        "value_kind": "string",
                    }
                ],
            }
        )
        assert isinstance(request.filters, FilterTree)
        assert request.filters.op == BooleanOperator.AND

    def test_search_request_accepts_none_filters(self) -> None:
        request = SearchRequest()
        assert request.filters is None

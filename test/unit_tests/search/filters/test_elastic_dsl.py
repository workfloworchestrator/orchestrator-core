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

    def test_bool_must_not_single_term(self) -> None:
        leaf = _parse_and_get_leaf({"bool": {"must_not": [{"term": {"subscription.status": "terminated"}}]}})
        assert isinstance(leaf.condition, EqualityFilter)
        assert leaf.condition.op == FilterOp.NEQ
        assert leaf.condition.value == "terminated"

    def test_bool_must_not_single_range(self) -> None:
        leaf = _parse_and_get_leaf(
            {"bool": {"must_not": [{"range": {"subscription.start_date": {"gt": "2025-01-01"}}}]}}
        )
        assert isinstance(leaf.condition, DateValueFilter)
        assert leaf.condition.op == FilterOp.LTE

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
    def test_depth_limit_exceeded(self) -> None:
        inner: dict[str, Any] = {"term": {"field": "value"}}
        for _ in range(FilterTree.MAX_DEPTH + 1):
            inner = {"bool": {"must": [inner]}}

        es = ElasticQueryAdapter.validate_python(inner)
        with pytest.raises(ValueError, match="MAX_DEPTH"):
            elastic_to_filter_tree(es)

    def test_empty_bool_raises(self) -> None:
        with pytest.raises(ValidationError, match="at least one clause"):
            ElasticQueryAdapter.validate_python({"bool": {}})


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

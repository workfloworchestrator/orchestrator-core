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

ElasticQueryAdapter = TypeAdapter(ElasticQuery)


# ---------------------------------------------------------------------------
# term queries
# ---------------------------------------------------------------------------


class TestTermQuery:
    def test_term_string_value(self) -> None:
        es = ElasticQueryAdapter.validate_python({"term": {"subscription.status": "active"}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert leaf.path == "subscription.status"
        assert isinstance(leaf.condition, EqualityFilter)
        assert leaf.condition.op == FilterOp.EQ
        assert leaf.condition.value == "active"
        assert leaf.value_kind == UIType.STRING

    def test_term_boolean_value(self) -> None:
        es = ElasticQueryAdapter.validate_python({"term": {"subscription.insured": True}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, EqualityFilter)
        assert leaf.condition.value is True
        assert leaf.value_kind == UIType.BOOLEAN

    def test_term_uuid_value(self) -> None:
        uid = "550e8400-e29b-41d4-a716-446655440000"
        es = ElasticQueryAdapter.validate_python({"term": {"subscription.customer_id": uid}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert leaf.condition.value == uid
        assert leaf.value_kind == UIType.STRING


# ---------------------------------------------------------------------------
# range queries
# ---------------------------------------------------------------------------


class TestRangeQuery:
    def test_range_single_gt_date(self) -> None:
        es = ElasticQueryAdapter.validate_python({"range": {"subscription.start_date": {"gt": "2025-01-01"}}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, DateValueFilter)
        assert leaf.condition.op == FilterOp.GT
        assert leaf.condition.value == "2025-01-01"
        assert leaf.value_kind == UIType.DATETIME

    def test_range_single_lte_number(self) -> None:
        es = ElasticQueryAdapter.validate_python({"range": {"subscription.port_speed": {"lte": 1000}}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, NumericValueFilter)
        assert leaf.condition.op == FilterOp.LTE
        assert leaf.condition.value == 1000
        assert leaf.value_kind == UIType.NUMBER

    def test_range_between_dates(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {"range": {"subscription.start_date": {"gte": "2025-01-01", "lte": "2025-12-31"}}}
        )
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, DateRangeFilter)
        assert leaf.condition.op == FilterOp.BETWEEN
        assert leaf.condition.value.start == "2025-01-01"
        assert leaf.condition.value.end == "2025-12-31"
        assert leaf.value_kind == UIType.DATETIME

    def test_range_between_numbers(self) -> None:
        es = ElasticQueryAdapter.validate_python({"range": {"subscription.bandwidth": {"gte": 100, "lte": 10000}}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, NumericRangeFilter)
        assert leaf.condition.op == FilterOp.BETWEEN
        assert leaf.condition.value.start == 100
        assert leaf.condition.value.end == 10000
        assert leaf.value_kind == UIType.NUMBER


# ---------------------------------------------------------------------------
# wildcard queries
# ---------------------------------------------------------------------------


class TestWildcardQuery:
    def test_wildcard_pattern_conversion(self) -> None:
        es = ElasticQueryAdapter.validate_python({"wildcard": {"subscription.description": {"value": "*fiber*"}}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, StringFilter)
        assert leaf.condition.op == FilterOp.LIKE
        assert leaf.condition.value == "%fiber%"
        assert leaf.value_kind == UIType.STRING

    def test_wildcard_question_mark(self) -> None:
        es = ElasticQueryAdapter.validate_python({"wildcard": {"subscription.name": {"value": "node-?"}}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf.condition, StringFilter)
        assert leaf.condition.value == "node-_"


# ---------------------------------------------------------------------------
# exists queries
# ---------------------------------------------------------------------------


class TestExistsQuery:
    def test_exists_to_ltree_filter(self) -> None:
        es = ElasticQueryAdapter.validate_python({"exists": {"field": "node"}})
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert leaf.path == "*"
        assert isinstance(leaf.condition, LtreeFilter)
        assert leaf.condition.op == FilterOp.ENDS_WITH
        assert leaf.condition.value == "node"
        assert leaf.value_kind == UIType.COMPONENT


# ---------------------------------------------------------------------------
# bool queries
# ---------------------------------------------------------------------------


class TestBoolQuery:
    def test_bool_must_to_and_tree(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "must": [
                        {"term": {"subscription.status": "active"}},
                        {"term": {"subscription.product": "fiber"}},
                    ]
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.AND
        assert len(tree.children) == 2

    def test_bool_should_to_or_tree(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {
                "bool": {
                    "should": [
                        {"term": {"subscription.status": "active"}},
                        {"term": {"subscription.status": "provisioning"}},
                    ]
                }
            }
        )
        tree = elastic_to_filter_tree(es)
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.OR
        assert len(tree.children) == 2

    def test_bool_must_not_single_term(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {"bool": {"must_not": [{"term": {"subscription.status": "terminated"}}]}}
        )
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
        assert isinstance(leaf.condition, EqualityFilter)
        assert leaf.condition.op == FilterOp.NEQ
        assert leaf.condition.value == "terminated"

    def test_bool_must_not_single_range(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {"bool": {"must_not": [{"range": {"subscription.start_date": {"gt": "2025-01-01"}}}]}}
        )
        tree = elastic_to_filter_tree(es)
        leaf = tree.children[0]
        assert isinstance(leaf, PathFilter)
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
        # First child is the must clause
        must_leaf = tree.children[0]
        assert isinstance(must_leaf, PathFilter)
        assert must_leaf.condition.value == "fiber"
        # Second child is the inverted must_not
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
        # Second child is the nested OR
        nested = tree.children[1]
        assert isinstance(nested, FilterTree)
        assert nested.op == BooleanOperator.OR
        assert len(nested.children) == 2

    def test_bool_must_not_range_between_inverts_to_or(self) -> None:
        es = ElasticQueryAdapter.validate_python(
            {"bool": {"must_not": [{"range": {"subscription.bandwidth": {"gte": 100, "lte": 10000}}}]}}
        )
        tree = elastic_to_filter_tree(es)
        # Between inversion produces an OR of < start, > end
        # The single must_not child is unwrapped, so the tree itself is the OR
        assert isinstance(tree, FilterTree)
        assert tree.op == BooleanOperator.OR
        assert len(tree.children) == 2
        # First child: LT start, Second child: GT end
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
    def test_infer_datetime(self) -> None:
        es = ElasticQueryAdapter.validate_python({"term": {"field": "2025-06-15"}})
        tree = elastic_to_filter_tree(es)
        assert tree.children[0].value_kind == UIType.DATETIME

    def test_infer_number(self) -> None:
        es = ElasticQueryAdapter.validate_python({"term": {"field": 42}})
        tree = elastic_to_filter_tree(es)
        assert tree.children[0].value_kind == UIType.NUMBER

    def test_infer_boolean(self) -> None:
        es = ElasticQueryAdapter.validate_python({"term": {"field": True}})
        tree = elastic_to_filter_tree(es)
        assert tree.children[0].value_kind == UIType.BOOLEAN

    def test_infer_string(self) -> None:
        es = ElasticQueryAdapter.validate_python({"term": {"field": "hello"}})
        tree = elastic_to_filter_tree(es)
        assert tree.children[0].value_kind == UIType.STRING


# ---------------------------------------------------------------------------
# validation / edge cases
# ---------------------------------------------------------------------------


class TestValidation:
    def test_depth_limit_exceeded(self) -> None:
        # Build a deeply nested bool query exceeding MAX_DEPTH
        inner: dict = {"term": {"field": "value"}}
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
    def test_search_request_accepts_elastic_dsl(self) -> None:
        request = SearchRequest(
            filters={  # type: ignore[arg-type]
                "bool": {
                    "must": [
                        {"term": {"subscription.status": "active"}},
                        {"range": {"subscription.start_date": {"gte": "2025-01-01"}}},
                    ]
                }
            }
        )
        assert isinstance(request.filters, FilterTree)
        assert request.filters.op == BooleanOperator.AND
        assert len(request.filters.children) == 2

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

    def test_search_request_accepts_simple_term_dsl(self) -> None:
        request = SearchRequest(filters={"term": {"subscription.status": "active"}})  # type: ignore[arg-type]
        assert isinstance(request.filters, FilterTree)
        assert len(request.filters.children) == 1

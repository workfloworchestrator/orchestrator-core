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

from orchestrator.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, PathFilter, StringFilter


@pytest.fixture
def path_filter_leaf() -> PathFilter:
    """Basic PathFilter leaf for building trees."""
    return PathFilter(
        path="subscription.status",
        condition=EqualityFilter(op=FilterOp.EQ, value="active"),
        value_kind=UIType.STRING,
    )


@pytest.fixture
def nested_filter_tree() -> FilterTree:
    """Nested FilterTree with multiple levels for testing tree operations."""
    return FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="subscription.status",
                condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            ),
            FilterTree(
                op=BooleanOperator.OR,
                children=[
                    PathFilter(
                        path="subscription.product.name",
                        condition=StringFilter(op=FilterOp.LIKE, value="%fiber%"),
                        value_kind=UIType.STRING,
                    ),
                    PathFilter(
                        path="subscription.customer_id",
                        condition=EqualityFilter(op=FilterOp.EQ, value="acme"),
                        value_kind=UIType.STRING,
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def es_dsl_term_query() -> dict[str, Any]:
    """Simple ES DSL term query."""
    return {"term": {"subscription.status": "active"}}


@pytest.fixture
def es_dsl_bool_must_query() -> dict[str, Any]:
    """ES DSL bool query with must clause."""
    return {
        "bool": {
            "must": [
                {"term": {"subscription.status": "active"}},
                {"range": {"subscription.start_date": {"gte": "2025-01-01"}}},
            ]
        }
    }


@pytest.fixture
def es_dsl_bool_should_query() -> dict[str, Any]:
    """ES DSL bool query with should clause."""
    return {
        "bool": {
            "should": [
                {"term": {"subscription.product": "fiber"}},
                {"term": {"subscription.product": "wireless"}},
            ]
        }
    }


@pytest.fixture
def es_dsl_nested_query() -> dict[str, Any]:
    """ES DSL nested bool query combining must and should."""
    return {
        "bool": {
            "must": [
                {"term": {"subscription.status": "active"}},
                {
                    "bool": {
                        "should": [
                            {"wildcard": {"subscription.description": {"value": "*fiber*"}}},
                            {"exists": {"field": "node"}},
                        ]
                    }
                },
            ]
        }
    }

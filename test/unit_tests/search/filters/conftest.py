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

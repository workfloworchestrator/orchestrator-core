# Copyright 2019-2026 SURF, GÉANT.
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

from uuid import UUID

import pytest

from orchestrator.core.graphql.search_inputs import (
    FilterConditionInput,
    FilterTreeInput,
    PathFilterInput,
    ResourceSearchInput,
    SearchInput,
    StructuredOrderByInput,
)
from orchestrator.core.search.core.types import BooleanOperator, EntityType, FilterOp, RetrieverType, UIType
from orchestrator.core.search.filters.base import EqualityFilter, FilterTree, PathFilter, StringFilter
from orchestrator.core.search.filters.date_filters import DateRangeFilter, DateValueFilter
from orchestrator.core.search.filters.ltree_filters import LtreeFilter
from orchestrator.core.search.filters.numeric_filter import NumericRangeFilter, NumericValueFilter
from orchestrator.core.search.query.mixins import OrderDirection
from orchestrator.core.search.query.queries import SelectQuery


@pytest.mark.parametrize(
    "op, value_kind, value, range_start, range_end, expected_type",
    [
        pytest.param(FilterOp.EQ, UIType.STRING, "active", None, None, EqualityFilter, id="eq-string"),
        pytest.param(FilterOp.NEQ, UIType.STRING, "inactive", None, None, EqualityFilter, id="neq-string"),
        pytest.param(FilterOp.LIKE, UIType.STRING, "%test%", None, None, StringFilter, id="like-string"),
        pytest.param(FilterOp.GTE, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="gte-datetime"),
        pytest.param(FilterOp.GTE, UIType.NUMBER, "42", None, None, NumericValueFilter, id="gte-number"),
        pytest.param(FilterOp.LT, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="lt-datetime"),
        pytest.param(FilterOp.LTE, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="lte-datetime"),
        pytest.param(FilterOp.GT, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="gt-datetime"),
        pytest.param(
            FilterOp.BETWEEN, UIType.DATETIME, None, "2025-01-01", "2025-12-31", DateRangeFilter, id="between-datetime"
        ),
        pytest.param(FilterOp.BETWEEN, UIType.NUMBER, None, "10", "100", NumericRangeFilter, id="between-number"),
        pytest.param(FilterOp.MATCHES_LQUERY, UIType.COMPONENT, "test", None, None, LtreeFilter, id="matches-lquery"),
        pytest.param(FilterOp.IS_ANCESTOR, UIType.COMPONENT, "test", None, None, LtreeFilter, id="is-ancestor"),
        pytest.param(FilterOp.IS_DESCENDANT, UIType.COMPONENT, "test", None, None, LtreeFilter, id="is-descendant"),
        pytest.param(FilterOp.PATH_MATCH, UIType.COMPONENT, "test", None, None, LtreeFilter, id="path-match"),
        pytest.param(FilterOp.HAS_COMPONENT, UIType.COMPONENT, "node", None, None, LtreeFilter, id="has-component"),
        pytest.param(
            FilterOp.NOT_HAS_COMPONENT, UIType.COMPONENT, "node", None, None, LtreeFilter, id="not-has-component"
        ),
        pytest.param(FilterOp.ENDS_WITH, UIType.COMPONENT, "test", None, None, LtreeFilter, id="ends-with"),
    ],
)
def test_filter_condition_dispatch(
    op: FilterOp,
    value_kind: UIType,
    value: str | None,
    range_start: str | None,
    range_end: str | None,
    expected_type: type,
) -> None:
    condition = FilterConditionInput(op=op, value=value, range_start=range_start, range_end=range_end)
    result = condition.to_pydantic(value_kind=value_kind)
    assert isinstance(result, expected_type), f"Expected {expected_type.__name__}, got {type(result).__name__}"


def test_path_filter_input_to_pydantic() -> None:
    path_input = PathFilterInput(
        path="subscription.status",
        condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
        value_kind=UIType.STRING,
    )
    result = path_input.to_pydantic()
    assert isinstance(result, PathFilter)
    assert result.path == "subscription.status"
    assert result.value_kind == UIType.STRING
    assert isinstance(result.condition, EqualityFilter)


def test_filter_tree_input_flat() -> None:
    tree_input = FilterTreeInput(
        op=BooleanOperator.AND,
        filters=[
            PathFilterInput(
                path="subscription.status",
                condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            ),
            PathFilterInput(
                path="subscription.product.name",
                condition=FilterConditionInput(op=FilterOp.LIKE, value="%fiber%"),
                value_kind=UIType.STRING,
            ),
        ],
    )
    result = tree_input.to_pydantic()
    assert isinstance(result, FilterTree)
    assert result.op == BooleanOperator.AND
    assert len(result.children) == 2
    assert all(isinstance(c, PathFilter) for c in result.children)


def test_filter_tree_input_nested() -> None:
    tree_input = FilterTreeInput(
        op=BooleanOperator.AND,
        filters=[
            PathFilterInput(
                path="subscription.start_date",
                condition=FilterConditionInput(op=FilterOp.GTE, value="2024-01-01"),
                value_kind=UIType.DATETIME,
            ),
        ],
        groups=[
            FilterTreeInput(
                op=BooleanOperator.OR,
                filters=[
                    PathFilterInput(
                        path="subscription.product.name",
                        condition=FilterConditionInput(op=FilterOp.LIKE, value="%fiber%"),
                        value_kind=UIType.STRING,
                    ),
                    PathFilterInput(
                        path="subscription.customer_id",
                        condition=FilterConditionInput(op=FilterOp.EQ, value="Surf"),
                        value_kind=UIType.STRING,
                    ),
                ],
            ),
        ],
    )
    result = tree_input.to_pydantic()
    assert isinstance(result, FilterTree)
    assert result.op == BooleanOperator.AND
    assert len(result.children) == 2

    assert isinstance(result.children[0], PathFilter)

    nested = result.children[1]
    assert isinstance(nested, FilterTree)
    assert nested.op == BooleanOperator.OR
    assert len(nested.children) == 2


def test_search_input_to_select_query() -> None:
    search = SearchInput(
        query="fiber",
        filters=FilterTreeInput(
            op=BooleanOperator.AND,
            filters=[
                PathFilterInput(
                    path="subscription.status",
                    condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
                    value_kind=UIType.STRING,
                ),
            ],
        ),
        limit=5,
        retriever=RetrieverType.FUZZY,
        response_columns=["subscription.status", "subscription.product.name"],
    )
    result = search.to_select_query(EntityType.SUBSCRIPTION)
    assert isinstance(result, SelectQuery)
    assert result.entity_type == EntityType.SUBSCRIPTION
    assert result.query_text == "fiber"
    assert result.limit == 5
    assert result.retriever == RetrieverType.FUZZY
    assert result.filters is not None
    assert result.response_columns == ["subscription.status", "subscription.product.name"]


def test_search_input_minimal() -> None:
    search = SearchInput()
    result = search.to_select_query(EntityType.PRODUCT)
    assert isinstance(result, SelectQuery)
    assert result.entity_type == EntityType.PRODUCT
    assert result.query_text is None
    assert result.filters is None
    assert result.limit == 10
    assert result.retriever is None
    assert result.order_by is None
    assert result.response_columns is None


def test_search_input_with_order_by() -> None:
    search = SearchInput(
        order_by=StructuredOrderByInput(element="subscription.start_date", direction=OrderDirection.DESC),
    )
    result = search.to_select_query(EntityType.SUBSCRIPTION)
    assert result.order_by is not None
    assert result.order_by.element == "subscription.start_date"
    assert result.order_by.direction == OrderDirection.DESC


def test_comparison_op_invalid_value_kind_raises() -> None:
    condition = FilterConditionInput(op=FilterOp.GT, value="42")
    with pytest.raises(ValueError, match="Operator .* is not valid for value_kind"):
        condition.to_pydantic(value_kind=UIType.STRING)


def test_empty_filter_tree_raises() -> None:
    tree_input = FilterTreeInput(op=BooleanOperator.AND)
    with pytest.raises(ValueError, match="FilterTreeInput must contain at least one filter or group"):
        tree_input.to_pydantic()


ELASTIC_STATUS_FILTER = {"bool": {"should": [{"term": {"subscription.status": "active"}}]}}


def test_search_input_converts_elastic_filters():
    result = SearchInput(elastic_filters=ELASTIC_STATUS_FILTER).to_select_query(EntityType.SUBSCRIPTION)

    assert result.filters == FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="subscription.status",
                condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            )
        ],
    )


def test_search_input_rejects_invalid_elastic_filters():
    """The DSL itself is covered by test_elastic_dsl.py; this pins that the JSON input is validated against it."""
    with pytest.raises(ValueError):
        SearchInput(elastic_filters={"match": {"subscription.status": "active"}}).to_select_query(
            EntityType.SUBSCRIPTION
        )


def test_search_input_rejects_both_filter_formats():
    search = SearchInput(
        filters=FilterTreeInput(
            filters=[
                PathFilterInput(
                    path="subscription.status",
                    condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
                    value_kind=UIType.STRING,
                )
            ]
        ),
        elastic_filters=ELASTIC_STATUS_FILTER,
    )

    with pytest.raises(ValueError, match="Pass either filters or elasticFilters, not both"):
        search.to_select_query(EntityType.SUBSCRIPTION)


@pytest.mark.parametrize("search_input", [SearchInput, ResourceSearchInput])
def test_search_input_rejects_order_by_with_query(search_input):
    search = search_input(
        query="example",
        order_by=StructuredOrderByInput(element="subscription.start_date", direction=OrderDirection.DESC),
    )

    with pytest.raises(ValueError, match="order_by can only be set when query is empty"):
        search.to_select_query(EntityType.SUBSCRIPTION, 10)


_A, _B, _C = (UUID(int=n) for n in range(1, 4))


@pytest.mark.parametrize(
    "client_ids, allowed_ids, expected",
    [
        pytest.param(None, None, None, id="unscoped"),
        pytest.param([_A], None, [_A], id="client-only"),
        pytest.param(None, [_A, _B], [_A, _B], id="relation-only"),
        pytest.param([_A, _C], [_A, _B], [_A], id="client-narrows-relation"),
        pytest.param([_C], [_A, _B], [], id="client-cannot-widen"),
    ],
)
def test_resource_search_within_never_widens(client_ids, allowed_ids, expected):
    assert ResourceSearchInput(entity_ids=client_ids).within(allowed_ids).entity_ids == expected

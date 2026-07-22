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

"""Tests for SearchRequest validation: limit bounds, order_by/query exclusivity, filter conversion, and to_query."""

from unittest.mock import patch

import pytest
from pydantic import ConfigDict, ValidationError

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.schemas.search_requests import SearchRequest
from orchestrator.core.search.core.types import EntityType, RetrieverType, UIType
from orchestrator.core.search.indexing.field_types import _subscription_field_types
from orchestrator.core.search.query.mixins import StructuredOrderBy


@pytest.mark.parametrize(
    "limit",
    [
        pytest.param(0, id="below-min"),
        pytest.param(999, id="above-max"),
    ],
)
def test_limit_boundary_violations_raise(limit: int) -> None:
    with pytest.raises(ValidationError):
        SearchRequest(limit=limit)


@pytest.mark.parametrize(
    "limit",
    [
        pytest.param(1, id="min"),
        pytest.param(30, id="max"),
    ],
)
def test_limit_boundaries_succeed(limit: int) -> None:
    assert SearchRequest(limit=limit).limit == limit


def test_order_by_with_query_raises() -> None:
    with pytest.raises(ValidationError, match="order_by can only be set when query is empty"):
        SearchRequest(query="hello", order_by=StructuredOrderBy(element="name"))


def test_order_by_without_query_succeeds() -> None:
    schema = SearchRequest(order_by=StructuredOrderBy(element="name"))
    assert schema.order_by is not None


@pytest.mark.parametrize(
    "elastic_filter",
    [
        pytest.param({"term": {"status": "active"}}, id="term"),
        pytest.param({"bool": {"must": [{"term": {"status": "active"}}]}}, id="bool"),
        pytest.param({"range": {"created_at": {"gte": "2024-01-01"}}}, id="range"),
        pytest.param({"wildcard": {"name": {"value": "test*"}}}, id="wildcard"),
        pytest.param({"exists": {"field": "end_date"}}, id="exists"),
    ],
)
def test_elastic_dsl_filter_converted(elastic_filter: dict) -> None:
    schema = SearchRequest(filters=elastic_filter)  # type: ignore[arg-type]
    assert schema.to_query(EntityType.SUBSCRIPTION).filters is not None


@pytest.mark.parametrize(
    "entity_type",
    [EntityType.SUBSCRIPTION, EntityType.PRODUCT, EntityType.WORKFLOW, EntityType.PROCESS],
    ids=["subscription", "product", "workflow", "process"],
)
def test_to_query_propagates_entity_type(entity_type: EntityType) -> None:
    assert SearchRequest().to_query(entity_type).entity_type == entity_type


def test_to_query_propagates_fields() -> None:
    schema = SearchRequest(query="search text", limit=15, response_columns=["name", "status"])
    query = schema.to_query(EntityType.SUBSCRIPTION)
    assert query.query_text == "search text"
    assert query.limit == 15
    assert query.response_columns == ["name", "status"]


def test_to_query_resolves_digit_only_string_term_from_subscription_schema() -> None:
    class VlanRange(str):
        pass

    class VlanRangeSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        vlanrange: VlanRange | None = None

    _subscription_field_types.cache_clear()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"VLAN": VlanRangeSubscription}, clear=True):
        request = SearchRequest(filters={"term": {"vlanrange": "26"}})  # type: ignore[arg-type]
        query = request.to_query(EntityType.SUBSCRIPTION)

    _subscription_field_types.cache_clear()
    assert query.filters is not None
    leaf = query.filters.children[0]
    assert leaf.value_kind == UIType.STRING


def test_to_query_preserves_native_filter_tree() -> None:
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

    query = request.to_query(EntityType.SUBSCRIPTION)
    assert query.filters == request.filters


@pytest.mark.parametrize(
    "retriever",
    [RetrieverType.FUZZY, RetrieverType.SEMANTIC, RetrieverType.HYBRID],
    ids=["fuzzy", "semantic", "hybrid"],
)
def test_all_retriever_types_accepted(retriever: RetrieverType) -> None:
    assert SearchRequest(retriever=retriever).retriever == retriever

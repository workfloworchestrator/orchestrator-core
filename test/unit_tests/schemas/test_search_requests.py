# Copyright 2019-2025 SURF.
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

import pytest
from pydantic import ValidationError

pytest.importorskip("orchestrator.search.core.types", reason="search extra not installed")

from orchestrator.schemas.search_requests import SearchRequest  # noqa: E402
from orchestrator.search.core.types import EntityType, RetrieverType  # noqa: E402
from orchestrator.search.query.mixins import StructuredOrderBy  # noqa: E402


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
    assert schema.filters is not None


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


@pytest.mark.parametrize(
    "retriever",
    [RetrieverType.FUZZY, RetrieverType.SEMANTIC, RetrieverType.HYBRID],
    ids=["fuzzy", "semantic", "hybrid"],
)
def test_all_retriever_types_accepted(retriever: RetrieverType) -> None:
    assert SearchRequest(retriever=retriever).retriever == retriever

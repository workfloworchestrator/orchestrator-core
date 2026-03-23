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

import pytest
from pydantic import ValidationError

pytest.importorskip("orchestrator.search.core.types", reason="search extra not installed")

from orchestrator.schemas.search_requests import SearchRequest  # noqa: E402
from orchestrator.search.core.types import EntityType, RetrieverType  # noqa: E402
from orchestrator.search.query.mixins import StructuredOrderBy  # noqa: E402


class TestSearchRequestInstantiation:
    def test_instantiate_empty_request_uses_defaults(self) -> None:
        schema = SearchRequest()
        assert schema.filters is None
        assert schema.query is None
        assert schema.limit == 10  # DEFAULT_LIMIT
        assert schema.retriever is None
        assert schema.order_by is None
        assert schema.response_columns is None

    def test_instantiate_with_query_succeeds(self) -> None:
        schema = SearchRequest(query="test search")
        assert schema.query == "test search"

    def test_instantiate_with_limit_succeeds(self) -> None:
        schema = SearchRequest(limit=20)
        assert schema.limit == 20

    def test_instantiate_with_response_columns_succeeds(self) -> None:
        schema = SearchRequest(response_columns=["name", "status"])
        assert schema.response_columns == ["name", "status"]

    @pytest.mark.parametrize(
        "retriever",
        [RetrieverType.FUZZY, RetrieverType.SEMANTIC, RetrieverType.HYBRID],
        ids=["fuzzy", "semantic", "hybrid"],
    )
    def test_instantiate_all_retriever_types_succeeds(self, retriever: RetrieverType) -> None:
        schema = SearchRequest(retriever=retriever)
        assert schema.retriever == retriever


class TestSearchRequestValidation:
    def test_limit_below_min_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchRequest(limit=0)

    def test_limit_above_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchRequest(limit=999)

    def test_limit_at_min_boundary_succeeds(self) -> None:
        schema = SearchRequest(limit=1)
        assert schema.limit == 1

    def test_limit_at_max_boundary_succeeds(self) -> None:
        schema = SearchRequest(limit=30)
        assert schema.limit == 30

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            SearchRequest(unknown_field="value")  # type: ignore[call-arg]

    def test_order_by_with_query_raises(self) -> None:
        with pytest.raises(ValidationError, match="order_by can only be set when query is empty"):
            SearchRequest(query="hello", order_by=StructuredOrderBy(element="name"))

    def test_order_by_without_query_succeeds(self) -> None:
        schema = SearchRequest(order_by=StructuredOrderBy(element="name"))
        assert schema.order_by is not None

    def test_query_without_order_by_succeeds(self) -> None:
        schema = SearchRequest(query="find me")
        assert schema.query == "find me"
        assert schema.order_by is None


class TestSearchRequestFilterConversion:
    def test_filter_tree_passthrough_as_none(self) -> None:
        schema = SearchRequest(filters=None)
        assert schema.filters is None

    def test_elastic_dsl_term_filter_converted(self) -> None:
        schema = SearchRequest(filters={"term": {"status": "active"}})  # type: ignore[arg-type]
        assert schema.filters is not None

    def test_elastic_dsl_bool_filter_converted(self) -> None:
        schema = SearchRequest(filters={"bool": {"must": [{"term": {"status": "active"}}]}})  # type: ignore[arg-type]
        assert schema.filters is not None

    def test_elastic_dsl_range_filter_converted(self) -> None:
        schema = SearchRequest(filters={"range": {"created_at": {"gte": "2024-01-01"}}})  # type: ignore[arg-type]
        assert schema.filters is not None

    def test_elastic_dsl_wildcard_filter_converted(self) -> None:
        schema = SearchRequest(filters={"wildcard": {"name": {"value": "test*"}}})  # type: ignore[arg-type]
        assert schema.filters is not None

    def test_elastic_dsl_exists_filter_converted(self) -> None:
        schema = SearchRequest(filters={"exists": {"field": "end_date"}})  # type: ignore[arg-type]
        assert schema.filters is not None


class TestSearchRequestToQuery:
    def test_to_query_returns_select_query(self) -> None:
        from orchestrator.search.query.queries import SelectQuery

        schema = SearchRequest(query="test")
        query = schema.to_query(EntityType.SUBSCRIPTION)
        assert isinstance(query, SelectQuery)

    def test_to_query_propagates_entity_type(self) -> None:
        schema = SearchRequest()
        query = schema.to_query(EntityType.PRODUCT)
        assert query.entity_type == EntityType.PRODUCT

    def test_to_query_propagates_limit(self) -> None:
        schema = SearchRequest(limit=15)
        query = schema.to_query(EntityType.SUBSCRIPTION)
        assert query.limit == 15

    def test_to_query_propagates_query_text(self) -> None:
        schema = SearchRequest(query="some search text")
        query = schema.to_query(EntityType.SUBSCRIPTION)
        assert query.query_text == "some search text"

    def test_to_query_propagates_response_columns(self) -> None:
        schema = SearchRequest(response_columns=["name", "status"])
        query = schema.to_query(EntityType.SUBSCRIPTION)
        assert query.response_columns == ["name", "status"]

    @pytest.mark.parametrize(
        "entity_type",
        [EntityType.SUBSCRIPTION, EntityType.PRODUCT, EntityType.WORKFLOW, EntityType.PROCESS],
        ids=["subscription", "product", "workflow", "process"],
    )
    def test_to_query_all_entity_types_succeed(self, entity_type: EntityType) -> None:
        schema = SearchRequest()
        query = schema.to_query(entity_type)
        assert query.entity_type == entity_type

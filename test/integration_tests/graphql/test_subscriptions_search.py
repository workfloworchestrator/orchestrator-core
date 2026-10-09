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
"""Tests for the `search` argument of the `subscriptions` query.

Search runs filter-only (structured retriever) against hand-written index rows, so no embeddings are needed.
"""

import json
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from more_itertools import one
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.query.state import QueryState
from orchestrator.core.search.retrieval.pagination import PageCursor
from test.integration_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS

SUBSCRIPTIONS_SEARCH_QUERY = """
query SubscriptionsSearch(
    $search: ResourceSearchInput,
    $filterBy: [GraphqlFilter!],
    $sortBy: [GraphqlSort!],
    $query: String,
    $first: Int,
    $after: Int
) {
    subscriptions(search: $search, filterBy: $filterBy, sortBy: $sortBy, query: $query, first: $first, after: $after) {
        page {
            subscriptionId
        }
        searchEdges {
            node {
                subscriptionId
                description
            }
            score
            perfectMatch
            matchingFields {
                path
                text
                highlightIndices
            }
        }
        searchMetadata {
            searchType
        }
        nextPageCursor
        pageInfo {
            hasNextPage
            hasPreviousPage
            totalItems
        }
    }
}
"""

STATUS_FILTER = {
    "op": "AND",
    "filters": [{"path": "subscription.status", "condition": {"op": "EQ", "value": "active"}, "valueKind": "STRING"}],
}


def _index_row(entity_id: UUID, path: str, value: str) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        entity_title=f"title {entity_id}",
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
    )


@pytest.fixture
def indexed_subscription_ids(product_type_1_subscriptions_factory) -> list[UUID]:
    """Three subscriptions indexed as active plus one indexed as terminated, which the status filter excludes."""
    subscription_ids = [UUID(sub_id) for sub_id in product_type_1_subscriptions_factory(4)]
    active, terminated = subscription_ids[:3], subscription_ids[3]
    db.session.add_all(
        [_index_row(sub_id, "subscription.status", "active") for sub_id in active]
        + [_index_row(terminated, "subscription.status", "terminated")]
    )
    db.session.commit()
    return active


def _post(test_client_graphql, **variables) -> dict:
    data = json.dumps({"query": SUBSCRIPTIONS_SEARCH_QUERY, "variables": variables})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    return response.json()


def test_search_returns_scored_edges_without_page(test_client_graphql, indexed_subscription_ids):
    result = _post(test_client_graphql, search={"filters": STATUS_FILTER, "limit": 10})

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    edges = subscriptions["searchEdges"]
    edge_ids = [edge["node"]["subscriptionId"] for edge in edges]
    assert sorted(edge_ids) == sorted(str(sub_id) for sub_id in indexed_subscription_ids)
    assert subscriptions["page"] is None
    assert all(edge["matchingFields"][0]["path"] == "subscription.status" for edge in edges)
    assert all(edge["matchingFields"][0]["text"] == "active" for edge in edges)
    assert subscriptions["searchMetadata"]["searchType"] == "structured"
    assert subscriptions["nextPageCursor"] is None
    assert subscriptions["pageInfo"] == {"hasNextPage": False, "hasPreviousPage": False, "totalItems": 3}


def test_search_accepts_elastic_filters_from_query_builder(test_client_graphql, indexed_subscription_ids):
    elastic_filters = {"bool": {"should": [{"term": {"subscription.status": "active"}}]}}

    result = _post(test_client_graphql, search={"elasticFilters": elastic_filters, "limit": 10})

    assert "errors" not in result
    edge_ids = [edge["node"]["subscriptionId"] for edge in result["data"]["subscriptions"]["searchEdges"]]
    assert sorted(edge_ids) == sorted(str(sub_id) for sub_id in indexed_subscription_ids)


def test_search_cursor_pages_through_hits(test_client_graphql, indexed_subscription_ids):
    first_page = _post(test_client_graphql, search={"filters": STATUS_FILTER, "limit": 2})["data"]["subscriptions"]
    cursor = first_page["nextPageCursor"]

    assert first_page["pageInfo"]["hasNextPage"] is True
    assert cursor is not None

    second = _post(test_client_graphql, search={"cursor": cursor})
    assert "errors" not in second
    second_page = second["data"]["subscriptions"]
    seen = [edge["node"]["subscriptionId"] for edge in first_page["searchEdges"] + second_page["searchEdges"]]
    assert sorted(seen) == sorted(str(sub_id) for sub_id in indexed_subscription_ids)
    assert second_page["pageInfo"]["hasPreviousPage"] is True
    assert second_page["pageInfo"]["hasNextPage"] is False
    assert second_page["nextPageCursor"] is None


def test_search_skips_hits_whose_subscription_no_longer_exists(test_client_graphql, indexed_subscription_ids):
    db.session.add(_index_row(uuid4(), "subscription.status", "active"))
    db.session.commit()

    result = _post(test_client_graphql, search={"filters": STATUS_FILTER, "limit": 10})

    assert "errors" not in result
    edge_ids = [edge["node"]["subscriptionId"] for edge in result["data"]["subscriptions"]["searchEdges"]]
    assert sorted(edge_ids) == sorted(str(sub_id) for sub_id in indexed_subscription_ids)


def test_search_without_criteria_returns_empty_edges(test_client_graphql, indexed_subscription_ids):
    result = _post(test_client_graphql, search={})

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    assert subscriptions["searchEdges"] == []
    assert subscriptions["page"] is None
    assert subscriptions["nextPageCursor"] is None


def test_without_search_the_search_fields_are_null(test_client_graphql, indexed_subscription_ids):
    result = _post(test_client_graphql, first=2)

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    assert len(subscriptions["page"]) == 2
    assert subscriptions["searchEdges"] is None
    assert subscriptions["searchMetadata"] is None
    assert subscriptions["nextPageCursor"] is None


@pytest.mark.parametrize(
    "other_arguments, conflicting",
    [
        pytest.param({"filterBy": [{"field": "status", "value": "active"}]}, "filterBy", id="filterBy"),
        pytest.param({"sortBy": [{"field": "startDate", "order": "ASC"}]}, "sortBy", id="sortBy"),
        pytest.param({"query": "active"}, "query", id="query"),
        pytest.param({"first": 5}, "first", id="first"),
        pytest.param({"after": 5}, "after", id="after"),
        pytest.param({"first": 5, "query": "active"}, "first, query", id="multiple"),
    ],
)
def test_search_combined_with_other_arguments_is_rejected(test_client_graphql, other_arguments, conflicting):
    result = _post(test_client_graphql, search={"filters": STATUS_FILTER}, **other_arguments)

    assert result["data"] is None
    assert result["errors"][0]["message"] == f"'search' cannot be combined with {conflicting}"
    assert result["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "search, code",
    [
        pytest.param({"cursor": "not-a-cursor"}, "VALIDATION_ERROR", id="malformed-cursor"),
        pytest.param({"retriever": "FUZZY"}, "VALIDATION_ERROR", id="retriever-without-query"),
        pytest.param({"limit": 0}, "VALIDATION_ERROR", id="limit-below-minimum"),
        pytest.param({"elasticFilters": {"bool": {}}}, "VALIDATION_ERROR", id="invalid-elastic-filters"),
        pytest.param(
            {"cursor": PageCursor(score=1.0, id=str(uuid4()), query_id=uuid4()).encode()},
            "NOT_FOUND",
            id="cursor-of-unknown-query",
        ),
    ],
)
def test_invalid_search_returns_graphql_error(test_client_graphql, search, code):
    result = _post(test_client_graphql, search=search)

    assert result["data"] is None
    error = result["errors"][0]
    assert error["message"] != "Internal Server Error"
    assert error["extensions"]["code"] == code


async def test_cursor_of_other_entity_type_is_rejected(test_client_graphql, async_session):
    query_id = await QueryState(query=SelectQuery(entity_type=EntityType.PROCESS), query_embedding=None).save(
        async_session
    )
    cursor = PageCursor(score=1.0, id=str(uuid4()), query_id=query_id).encode()

    result = _post(test_client_graphql, search={"cursor": cursor})

    assert result["data"] is None
    assert result["errors"][0]["message"] == "Cursor belongs to a PROCESS search"
    assert result["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"


def test_legacy_arguments_are_deprecated(test_client_graphql):
    introspection = """{
        __type(name: "Query") {
            fields { name args(includeDeprecated: true) { name isDeprecated deprecationReason } }
        }
    }"""
    data = json.dumps({"query": introspection})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)

    fields = response.json()["data"]["__type"]["fields"]
    args = {arg["name"]: arg for arg in one(f for f in fields if f["name"] == "subscriptions")["args"]}
    assert {name: arg["deprecationReason"] for name, arg in args.items() if arg["isDeprecated"]} == {
        "filterBy": "Use search.filters instead",
        "sortBy": "Use search.orderBy instead",
        "query": "Use search.query instead",
        "first": "Use search.limit instead",
        "after": "Use search.cursor instead",
    }

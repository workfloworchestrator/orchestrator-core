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
    result = _post(test_client_graphql, search={"filters": STATUS_FILTER}, first=10)

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    edges = subscriptions["searchEdges"]
    edge_ids = [edge["node"]["subscriptionId"] for edge in edges]
    assert sorted(edge_ids) == sorted(str(sub_id) for sub_id in indexed_subscription_ids)
    assert subscriptions["page"] == []
    assert all(edge["matchingFields"][0]["path"] == "subscription.status" for edge in edges)
    assert all(edge["matchingFields"][0]["text"] == "active" for edge in edges)
    assert subscriptions["searchMetadata"]["searchType"] == "structured"
    assert subscriptions["nextPageCursor"] is None
    assert subscriptions["pageInfo"] == {"hasNextPage": False, "hasPreviousPage": False, "totalItems": 3}


def test_search_accepts_elastic_filters_from_query_builder(test_client_graphql, indexed_subscription_ids):
    elastic_filters = {"bool": {"should": [{"term": {"subscription.status": "active"}}]}}

    result = _post(test_client_graphql, search={"elasticFilters": elastic_filters}, first=10)

    assert "errors" not in result
    edge_ids = [edge["node"]["subscriptionId"] for edge in result["data"]["subscriptions"]["searchEdges"]]
    assert sorted(edge_ids) == sorted(str(sub_id) for sub_id in indexed_subscription_ids)


def test_search_cursor_pages_through_hits(test_client_graphql, indexed_subscription_ids):
    first_page = _post(test_client_graphql, search={"filters": STATUS_FILTER}, first=2)["data"]["subscriptions"]
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


@pytest.mark.parametrize(
    "first, after, expected_slice, has_next_page",
    [
        pytest.param(2, 0, slice(0, 2), True, id="first-page"),
        pytest.param(2, 2, slice(2, 3), False, id="last-page"),
        pytest.param(1, 1, slice(1, 2), True, id="middle-page"),
        pytest.param(2, 5, slice(3, 3), False, id="past-the-end"),
    ],
)
def test_search_pages_by_offset(
    test_client_graphql, indexed_subscription_ids, first, after, expected_slice, has_next_page
):
    ordered = sorted(str(sub_id) for sub_id in indexed_subscription_ids)

    result = _post(test_client_graphql, search={"filters": STATUS_FILTER}, first=first, after=after)

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    assert [edge["node"]["subscriptionId"] for edge in subscriptions["searchEdges"]] == ordered[expected_slice]
    assert subscriptions["pageInfo"]["hasNextPage"] is has_next_page
    assert subscriptions["pageInfo"]["hasPreviousPage"] is bool(after)


def test_cursor_page_keeps_page_size_of_first_page(test_client_graphql, indexed_subscription_ids):
    first_page = _post(test_client_graphql, search={"filters": STATUS_FILTER}, first=1)["data"]["subscriptions"]

    second_page = _post(test_client_graphql, search={"cursor": first_page["nextPageCursor"]}, first=2)

    assert "errors" not in second_page
    assert len(second_page["data"]["subscriptions"]["searchEdges"]) == 1


def test_search_skips_hits_whose_subscription_no_longer_exists(test_client_graphql, indexed_subscription_ids):
    db.session.add(_index_row(uuid4(), "subscription.status", "active"))
    db.session.commit()

    result = _post(test_client_graphql, search={"filters": STATUS_FILTER}, first=10)

    assert "errors" not in result
    edge_ids = [edge["node"]["subscriptionId"] for edge in result["data"]["subscriptions"]["searchEdges"]]
    assert sorted(edge_ids) == sorted(str(sub_id) for sub_id in indexed_subscription_ids)


def test_search_without_criteria_returns_empty_edges(test_client_graphql, indexed_subscription_ids):
    result = _post(test_client_graphql, search={})

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    assert subscriptions["searchEdges"] == []
    assert subscriptions["page"] == []
    assert subscriptions["nextPageCursor"] is None


def test_without_search_the_search_fields_are_null(test_client_graphql, indexed_subscription_ids):
    result = _post(test_client_graphql, first=2)

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    assert len(subscriptions["page"]) == 2
    assert subscriptions["searchEdges"] == []
    assert subscriptions["searchMetadata"] is None
    assert subscriptions["nextPageCursor"] is None


@pytest.mark.parametrize("count", [pytest.param(2, id="some"), pytest.param(0, id="none")])
def test_search_entity_ids_restricts_hits(test_client_graphql, indexed_subscription_ids, count):
    wanted = [str(sub_id) for sub_id in indexed_subscription_ids[:count]]

    result = _post(test_client_graphql, search={"filters": STATUS_FILTER, "entityIds": wanted})

    assert "errors" not in result
    edge_ids = [edge["node"]["subscriptionId"] for edge in result["data"]["subscriptions"]["searchEdges"]]
    assert sorted(edge_ids) == sorted(wanted)


def test_search_entity_ids_apply_to_cursor_pages(test_client_graphql, indexed_subscription_ids):
    wanted = [str(sub_id) for sub_id in indexed_subscription_ids[:2]]
    first_page = _post(test_client_graphql, search={"filters": STATUS_FILTER, "entityIds": wanted}, first=1)
    cursor = first_page["data"]["subscriptions"]["nextPageCursor"]

    second_page = _post(test_client_graphql, search={"cursor": cursor, "entityIds": wanted})

    assert "errors" not in second_page
    pages = [first_page, second_page]
    seen = [edge["node"]["subscriptionId"] for page in pages for edge in page["data"]["subscriptions"]["searchEdges"]]
    assert sorted(seen) == sorted(wanted)
    assert second_page["data"]["subscriptions"]["nextPageCursor"] is None


@pytest.mark.parametrize(
    "other_arguments, conflicting",
    [
        pytest.param({"filterBy": [{"field": "status", "value": "active"}]}, "filterBy", id="filterBy"),
        pytest.param({"sortBy": [{"field": "startDate", "order": "ASC"}]}, "sortBy", id="sortBy"),
        pytest.param({"query": "active"}, "query", id="query"),
        pytest.param(
            {"filterBy": [{"field": "status", "value": "active"}], "query": "active"}, "filterBy, query", id="multiple"
        ),
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


@pytest.mark.parametrize(
    "search, paging, message",
    [
        pytest.param(
            {"query": "active"},
            {"after": 2},
            "An offset only works for structured search (filters without query text); page with a cursor",
            id="after-with-query-text",
        ),
        pytest.param(
            {"filters": STATUS_FILTER, "retriever": "FUZZY", "query": "active"},
            {"after": 2},
            "An offset only works for structured search (filters without query text); page with a cursor",
            id="after-with-forced-retriever",
        ),
        pytest.param(
            {"cursor": PageCursor(score=1.0, id=str(uuid4()), query_id=uuid4()).encode()},
            {"after": 2},
            "Page with either an offset or a cursor, not both",
            id="after-with-cursor",
        ),
        pytest.param({"filters": STATUS_FILTER}, {"first": 0}, None, id="first-below-minimum"),
    ],
)
def test_invalid_paging_returns_graphql_error(test_client_graphql, search, paging, message):
    result = _post(test_client_graphql, search=search, **paging)

    assert result["data"] is None
    error = result["errors"][0]
    assert error["extensions"]["code"] == "VALIDATION_ERROR"
    if message:
        assert error["message"] == message


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
    }


RELATION_SEARCH_QUERY = """
query RelationSearch($id: UUID!, $search: ResourceSearchInput, $filterBy: [GraphqlFilter!], $first: Int) {
    subscription(id: $id) {
        dependsOnSubscriptions(search: $search, filterBy: $filterBy, first: $first) {
            ...hits
        }
        inUseBySubscriptions(search: $search, filterBy: $filterBy, first: $first) {
            ...hits
        }
    }
}

fragment hits on SubscriptionInterfaceSearchConnection {
    page {
        subscriptionId
    }
    searchEdges {
        node {
            subscriptionId
        }
    }
    nextPageCursor
    pageInfo {
        hasNextPage
        totalItems
    }
}
"""


@pytest.fixture
def indexed_relations(
    product_type_1_subscriptions_factory,
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
) -> dict[str, UUID]:
    """The list union subscription depends on sub one and sub two, all indexed as active.

    Unrelated subscriptions are indexed as active too, so a search that ignores the relation would return them.
    """
    relations = {
        "sub_one": sub_one_subscription_1.subscription_id,
        "sub_two": sub_two_subscription_1.subscription_id,
        "list_union": product_sub_list_union_subscription_1,
    }
    unrelated = [UUID(sub_id) for sub_id in product_type_1_subscriptions_factory(3)]
    db.session.add_all(
        [_index_row(sub_id, "subscription.status", "active") for sub_id in [*relations.values(), *unrelated]]
    )
    db.session.commit()
    return relations


def _post_relations(test_client_graphql, subscription_id: UUID, **variables) -> dict:
    data = json.dumps({"query": RELATION_SEARCH_QUERY, "variables": {"id": str(subscription_id), **variables}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    return response.json()


def _edge_ids(connection: dict) -> list[str]:
    return [edge["node"]["subscriptionId"] for edge in connection["searchEdges"]]


@pytest.mark.parametrize(
    "subject, field, expected",
    [
        pytest.param("list_union", "dependsOnSubscriptions", ["sub_one", "sub_two"], id="depends-on"),
        pytest.param("sub_one", "inUseBySubscriptions", ["list_union"], id="in-use-by"),
    ],
)
def test_relation_search_is_scoped_to_related_subscriptions(
    test_client_graphql, indexed_relations, subject, field, expected
):
    result = _post_relations(
        test_client_graphql, indexed_relations[subject], search={"filters": STATUS_FILTER}, first=10
    )

    assert "errors" not in result
    connection = result["data"]["subscription"][field]
    assert sorted(_edge_ids(connection)) == sorted(str(indexed_relations[name]) for name in expected)
    assert connection["pageInfo"]["totalItems"] == len(expected)


def test_relation_search_without_relations_returns_empty_edges(test_client_graphql, indexed_relations):
    result = _post_relations(
        test_client_graphql, indexed_relations["list_union"], search={"filters": STATUS_FILTER}, first=10
    )

    assert "errors" not in result
    connection = result["data"]["subscription"]["inUseBySubscriptions"]
    assert connection["searchEdges"] == []
    assert connection["nextPageCursor"] is None


def test_relation_search_cursor_stays_within_relation(test_client_graphql, indexed_relations):
    list_union = indexed_relations["list_union"]
    first_page = _post_relations(test_client_graphql, list_union, search={"filters": STATUS_FILTER}, first=1)
    first = first_page["data"]["subscription"]["dependsOnSubscriptions"]

    assert first["pageInfo"] == {"hasNextPage": True, "totalItems": 2}

    second_page = _post_relations(test_client_graphql, list_union, search={"cursor": first["nextPageCursor"]})

    assert "errors" not in second_page
    second = second_page["data"]["subscription"]["dependsOnSubscriptions"]
    assert sorted(_edge_ids(first) + _edge_ids(second)) == sorted(
        str(indexed_relations[name]) for name in ("sub_one", "sub_two")
    )
    assert second["nextPageCursor"] is None


def test_relation_search_entity_ids_narrow_within_relation(test_client_graphql, indexed_relations):
    """Client ids intersect the relation: an unrelated id is never returned, an id in both is."""
    unrelated = str(uuid4())
    search = {"filters": STATUS_FILTER, "entityIds": [str(indexed_relations["sub_one"]), unrelated]}

    result = _post_relations(test_client_graphql, indexed_relations["list_union"], search=search)

    assert "errors" not in result
    connection = result["data"]["subscription"]["dependsOnSubscriptions"]
    assert _edge_ids(connection) == [str(indexed_relations["sub_one"])]


@pytest.mark.parametrize(
    "subject, field, expected",
    [
        pytest.param("list_union", "dependsOnSubscriptions", ["sub_one", "sub_two"], id="depends-on"),
        pytest.param("sub_one", "inUseBySubscriptions", ["list_union"], id="in-use-by"),
        pytest.param("list_union", "inUseBySubscriptions", [], id="no-relations"),
    ],
)
def test_relation_without_search_lists_related_subscriptions(
    test_client_graphql, indexed_relations, subject, field, expected
):
    result = _post_relations(test_client_graphql, indexed_relations[subject])

    assert "errors" not in result
    connection = result["data"]["subscription"][field]
    page_ids = [item["subscriptionId"] for item in connection["page"]]
    assert sorted(page_ids) == sorted(str(indexed_relations[name]) for name in expected)
    assert connection["searchEdges"] == []


def test_relation_search_combined_with_filter_by_is_rejected(test_client_graphql, indexed_relations):
    result = _post_relations(
        test_client_graphql,
        indexed_relations["sub_one"],
        search={"filters": STATUS_FILTER},
        filterBy=[{"field": "status", "value": "active"}],
    )

    assert result["errors"][0]["message"] == "'search' cannot be combined with filterBy"
    assert result["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

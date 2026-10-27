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
"""Tests for the `search` argument of the list resources and the relation fields.

Only what needs the search index, a saved query or the GraphQL transport lives here; the shared machinery's
branches are unit tested in test/unit_tests/graphql/test_resource_search.py and
test/unit_tests/search/query/test_page.py. Search runs filter-only (structured retriever) against hand-written index
rows, so no embeddings are needed.
"""

import json
from collections import namedtuple
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from more_itertools import one
from sqlalchemy import select
from sqlalchemy_utils import Ltree

from orchestrator.core.db import (
    ProcessSubscriptionTable,
    ProcessTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionTable,
    WorkflowTable,
    db,
)
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType
from test.integration_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


def _index_row(entity_type, entity_id, path, value="hit"):
    return AiSearchIndex(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=f"title {entity_id}",
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
    )


def _post(test_client_graphql, query, **variables):
    data = json.dumps({"query": query, "variables": variables})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    return response.json()


# --- Per-resource wiring --------------------------------------------------------------------------------------------
# Each resolver only names its entity type and its loader; this checks both for every resource. Resource-specific
# loader behaviour has its own test below.


Resource = namedtuple("Resource", ["field", "entity_type", "id_column", "gql_id", "path"])


RESOURCES = [
    pytest.param(
        Resource(
            "subscriptions",
            EntityType.SUBSCRIPTION,
            SubscriptionTable.subscription_id,
            "subscriptionId",
            "subscription.marker",
        ),
        id="subscriptions",
    ),
    pytest.param(
        Resource("processes", EntityType.PROCESS, ProcessTable.process_id, "processId", "process.marker"),
        id="processes",
    ),
    pytest.param(
        Resource("products", EntityType.PRODUCT, ProductTable.product_id, "productId", "product.marker"),
        id="products",
    ),
    pytest.param(
        Resource(
            "productBlocks",
            EntityType.PRODUCT_BLOCK,
            ProductBlockTable.product_block_id,
            "productBlockId",
            "product_block.marker",
        ),
        id="product-blocks",
    ),
    pytest.param(
        Resource(
            "resourceTypes",
            EntityType.RESOURCE_TYPE,
            ResourceTypeTable.resource_type_id,
            "resourceTypeId",
            "resource_type.marker",
        ),
        id="resource-types",
    ),
    pytest.param(
        Resource("workflows", EntityType.WORKFLOW, WorkflowTable.workflow_id, "workflowId", "workflow.marker"),
        id="workflows",
    ),
]


@pytest.fixture
def seeded_rows(
    mocked_processes,
    product_type_1_subscriptions_factory,
    generic_product_1,
    generic_product_2,
    generic_product_3,
    generic_product_block_3,
):
    """Rows of every resource; the fixtures above guarantee at least four of each."""
    product_type_1_subscriptions_factory(2)


@pytest.mark.parametrize("resource", RESOURCES)
def test_search_returns_hits_of_resource(test_client_graphql, seeded_rows, resource):
    *hits, miss = db.session.scalars(select(resource.id_column).order_by(resource.id_column).limit(4)).all()
    db.session.add_all(
        [_index_row(resource.entity_type, entity_id, resource.path) for entity_id in hits]
        + [_index_row(resource.entity_type, miss, resource.path, "miss")]
    )
    db.session.commit()
    query = f"""
    query ResourceSearch($search: ResourceSearchInput) {{
        {resource.field}(search: $search) {{
            page {{ {resource.gql_id} }}
            searchEdges {{ node {{ {resource.gql_id} }} }}
            searchMetadata {{ searchType }}
            pageInfo {{ hasNextPage hasPreviousPage totalItems }}
        }}
    }}
    """
    search_filter = {"path": resource.path, "condition": {"op": "EQ", "value": "hit"}, "valueKind": "STRING"}

    result = _post(test_client_graphql, query, search={"filters": {"op": "AND", "filters": [search_filter]}})

    assert "errors" not in result
    connection = result["data"][resource.field]
    edge_ids = [edge["node"][resource.gql_id] for edge in connection["searchEdges"]]
    assert sorted(edge_ids) == sorted(str(entity_id) for entity_id in hits)
    assert [node[resource.gql_id] for node in connection["page"]] == edge_ids
    assert connection["searchMetadata"]["searchType"] == "structured"
    assert connection["pageInfo"] == {"hasNextPage": False, "hasPreviousPage": False, "totalItems": 3}


# --- Resource-specific loaders --------------------------------------------------------------------------------------


def test_process_search_loads_details_when_requested(test_client_graphql, mocked_processes):
    """The process loader only loads steps when the query asks for details, also when asked under searchEdges."""
    db.session.add(_index_row(EntityType.PROCESS, mocked_processes[0], "process.marker"))
    db.session.commit()
    query = """
    query ProcessSearch($search: ResourceSearchInput) {
        processes(search: $search) {
            searchEdges { node { processId steps { name } } }
        }
    }
    """
    search_filter = {"path": "process.marker", "condition": {"op": "EQ", "value": "hit"}, "valueKind": "STRING"}

    result = _post(test_client_graphql, query, search={"filters": {"op": "AND", "filters": [search_filter]}})

    assert "errors" not in result
    node = one(result["data"]["processes"]["searchEdges"])["node"]
    assert [step["name"] for step in node["steps"]][:2] == ["Start", "Insert UUID in state"]


def test_subscription_search_returns_product_specific_type(test_client_graphql, generic_subscription_1):
    """The subscription loader resolves each hit to its product's GraphQL type, so product fields can be selected."""
    db.session.add(_index_row(EntityType.SUBSCRIPTION, generic_subscription_1, "subscription.marker"))
    db.session.commit()
    query = """
    query SubscriptionSearch($search: ResourceSearchInput) {
        subscriptions(search: $search) {
            searchEdges {
                node {
                    subscriptionId
                    ... on GenericProductOneSubscription { pb1 { rt1 } }
                }
            }
        }
    }
    """
    search_filter = {"path": "subscription.marker", "condition": {"op": "EQ", "value": "hit"}, "valueKind": "STRING"}

    result = _post(test_client_graphql, query, search={"filters": {"op": "AND", "filters": [search_filter]}})

    assert "errors" not in result
    node = one(result["data"]["subscriptions"]["searchEdges"])["node"]
    assert node == {"subscriptionId": generic_subscription_1, "pb1": {"rt1": "Value1"}}


# --- Shared search behaviour ----------------------------------------------------------------------------------------
# Identical for every resource, so run once against subscriptions. Branches that need no database are unit tested.

SUBSCRIPTIONS_SEARCH_QUERY = """
query SubscriptionsSearch($search: ResourceSearchInput, $filterBy: [GraphqlFilter!], $first: Int, $after: Int) {
    subscriptions(search: $search, filterBy: $filterBy, first: $first, after: $after) {
        page {
            subscriptionId
        }
        searchEdges {
            node {
                subscriptionId
            }
            matchingFields {
                path
                text
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

HIT_FILTER = {
    "op": "AND",
    "filters": [
        {"path": "subscription.marker", "condition": {"op": "EQ", "value": "hit"}, "valueKind": "STRING"},
    ],
}


@pytest.fixture
def indexed_subscription_ids(product_type_1_subscriptions_factory):
    """Three subscriptions indexed as hits plus one as a miss, which HIT_FILTER excludes; returned sorted by id."""
    *hits, miss = sorted(product_type_1_subscriptions_factory(4))
    db.session.add_all(
        [_index_row(EntityType.SUBSCRIPTION, sub_id, "subscription.marker") for sub_id in hits]
        + [_index_row(EntityType.SUBSCRIPTION, miss, "subscription.marker", "miss")]
    )
    db.session.commit()
    return hits


def test_search_returns_matching_fields(test_client_graphql, indexed_subscription_ids):
    result = _post(test_client_graphql, SUBSCRIPTIONS_SEARCH_QUERY, search={"filters": HIT_FILTER})

    assert "errors" not in result
    edges = result["data"]["subscriptions"]["searchEdges"]
    matching_fields = {edge["node"]["subscriptionId"]: edge["matchingFields"] for edge in edges}
    assert matching_fields == {
        sub_id: [{"path": "subscription.marker", "text": "hit"}] for sub_id in indexed_subscription_ids
    }
    assert result["data"]["subscriptions"]["nextPageCursor"] is None


def test_search_cursor_pages_through_hits(test_client_graphql, indexed_subscription_ids):
    first_response = _post(test_client_graphql, SUBSCRIPTIONS_SEARCH_QUERY, search={"filters": HIT_FILTER}, first=1)
    first_page = first_response["data"]["subscriptions"]

    second_response = _post(
        test_client_graphql, SUBSCRIPTIONS_SEARCH_QUERY, search={"cursor": first_page["nextPageCursor"]}, first=2
    )

    assert "errors" not in second_response
    second_page = second_response["data"]["subscriptions"]
    seen = [edge["node"]["subscriptionId"] for edge in first_page["searchEdges"] + second_page["searchEdges"]]
    assert len(seen) == 2
    assert set(seen) < set(indexed_subscription_ids)
    assert second_page["pageInfo"] == {"hasNextPage": True, "hasPreviousPage": True, "totalItems": 3}


@pytest.mark.parametrize(
    "first, after, expected_slice, has_next_page",
    [
        pytest.param(1, 1, slice(1, 2), True, id="middle-page"),
        pytest.param(2, 5, slice(3, 3), False, id="past-the-end"),
    ],
)
def test_search_pages_by_offset(
    test_client_graphql, indexed_subscription_ids, first, after, expected_slice, has_next_page
):
    result = _post(
        test_client_graphql, SUBSCRIPTIONS_SEARCH_QUERY, search={"filters": HIT_FILTER}, first=first, after=after
    )

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    edge_ids = [edge["node"]["subscriptionId"] for edge in subscriptions["searchEdges"]]
    assert edge_ids == indexed_subscription_ids[expected_slice]
    assert subscriptions["pageInfo"] == {
        "hasNextPage": has_next_page,
        "hasPreviousPage": True,
        "totalItems": len(indexed_subscription_ids),
    }


@pytest.mark.parametrize("count", [pytest.param(2, id="some"), pytest.param(0, id="none")])
def test_search_entity_ids_restricts_hits(test_client_graphql, indexed_subscription_ids, count):
    wanted = indexed_subscription_ids[:count]

    result = _post(test_client_graphql, SUBSCRIPTIONS_SEARCH_QUERY, search={"filters": HIT_FILTER, "entityIds": wanted})

    assert "errors" not in result
    edge_ids = [edge["node"]["subscriptionId"] for edge in result["data"]["subscriptions"]["searchEdges"]]
    assert sorted(edge_ids) == wanted


def test_without_search_the_search_fields_are_empty(test_client_graphql, indexed_subscription_ids):
    result = _post(test_client_graphql, SUBSCRIPTIONS_SEARCH_QUERY, first=2)

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    assert len(subscriptions["page"]) == 2
    assert subscriptions["searchEdges"] == []
    assert subscriptions["searchMetadata"] is None
    assert subscriptions["nextPageCursor"] is None


def test_search_on_repeated_field_is_resolved_once(test_client_graphql, indexed_subscription_ids):
    """Selections of one field without alias are merged, so the resolver sees several selected fields."""
    query = """
    query RepeatedSearch($search: ResourceSearchInput) {
        subscriptions(search: $search) { searchEdges { node { subscriptionId } } }
        subscriptions(search: $search) { pageInfo { totalItems } }
    }
    """

    result = _post(test_client_graphql, query, search={"filters": HIT_FILTER})

    assert "errors" not in result
    subscriptions = result["data"]["subscriptions"]
    assert sorted(edge["node"]["subscriptionId"] for edge in subscriptions["searchEdges"]) == indexed_subscription_ids
    assert subscriptions["pageInfo"]["totalItems"] == len(indexed_subscription_ids)


def test_search_rejects_order_by_unknown_element(test_client_graphql, indexed_subscription_ids):
    """Ordering by a path that is not indexed would sort every row by NULL and make cursor paging repeat page 1."""
    search = {"filters": HIT_FILTER, "orderBy": {"element": "subscription.unknown", "direction": "ASC"}}

    result = _post(test_client_graphql, SUBSCRIPTIONS_SEARCH_QUERY, search=search, first=2)

    assert result["data"] is None
    assert result["errors"][0]["message"] == "Element subscription.unknown is not a valid path"
    assert result["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"


def test_rejected_search_keeps_its_message_over_graphql(test_client_graphql):
    """ErrorHandlerExtension masks errors without a client error type as "Internal Server Error"."""
    result = _post(
        test_client_graphql,
        SUBSCRIPTIONS_SEARCH_QUERY,
        search={"filters": HIT_FILTER},
        filterBy=[{"field": "status", "value": "active"}],
    )

    assert result["data"] is None
    assert result["errors"][0]["message"] == "'search' cannot be combined with filterBy"
    assert result["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"


# --- Relation fields ------------------------------------------------------------------------------------------------
# Each relation narrows the search to its related ids with its own `within()` call.

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

fragment hits on SubscriptionInterfaceConnection {
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
):
    """The list union subscription depends on sub one and sub two, all indexed as hits.

    Unrelated subscriptions are indexed as hits too, so a search that ignores the relation would return them.
    """
    relations = {
        "sub_one": str(sub_one_subscription_1.subscription_id),
        "sub_two": str(sub_two_subscription_1.subscription_id),
        "list_union": str(product_sub_list_union_subscription_1),
    }
    unrelated = product_type_1_subscriptions_factory(3)
    db.session.add_all(
        [
            _index_row(EntityType.SUBSCRIPTION, sub_id, "subscription.marker")
            for sub_id in [*relations.values(), *unrelated]
        ]
    )
    db.session.commit()
    return relations


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
    result = _post(
        test_client_graphql, RELATION_SEARCH_QUERY, id=indexed_relations[subject], search={"filters": HIT_FILTER}
    )

    assert "errors" not in result
    connection = result["data"]["subscription"][field]
    edge_ids = [edge["node"]["subscriptionId"] for edge in connection["searchEdges"]]
    assert sorted(edge_ids) == sorted(indexed_relations[name] for name in expected)
    assert connection["pageInfo"]["totalItems"] == len(expected)


def test_relation_search_cursor_stays_within_relation(test_client_graphql, indexed_relations):
    """The relation's ids are not saved with the query, so the cursor page must narrow to them again."""
    list_union = indexed_relations["list_union"]
    first_response = _post(
        test_client_graphql, RELATION_SEARCH_QUERY, id=list_union, search={"filters": HIT_FILTER}, first=1
    )
    first_page = first_response["data"]["subscription"]["dependsOnSubscriptions"]

    assert first_page["pageInfo"] == {"hasNextPage": True, "totalItems": 2}

    second_response = _post(
        test_client_graphql, RELATION_SEARCH_QUERY, id=list_union, search={"cursor": first_page["nextPageCursor"]}
    )

    assert "errors" not in second_response
    second_page = second_response["data"]["subscription"]["dependsOnSubscriptions"]
    seen = [edge["node"]["subscriptionId"] for edge in first_page["searchEdges"] + second_page["searchEdges"]]
    assert sorted(seen) == sorted([indexed_relations["sub_one"], indexed_relations["sub_two"]])
    assert second_page["nextPageCursor"] is None


def test_relation_search_combined_with_filter_by_is_rejected(test_client_graphql, indexed_relations):
    """The relation passes its own filterBy on; the rejection must still see the client's."""
    result = _post(
        test_client_graphql,
        RELATION_SEARCH_QUERY,
        id=indexed_relations["sub_one"],
        search={"filters": HIT_FILTER},
        filterBy=[{"field": "status", "value": "active"}],
    )

    assert result["errors"][0]["message"] == "'search' cannot be combined with filterBy"
    assert result["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"


def test_subscription_processes_search_is_scoped_to_its_processes(
    test_client_graphql, mocked_processes, generic_subscription_1
):
    related = db.session.scalars(
        select(ProcessSubscriptionTable.process_id).where(
            ProcessSubscriptionTable.subscription_id == UUID(generic_subscription_1)
        )
    ).all()
    db.session.add_all(
        [_index_row(EntityType.PROCESS, process_id, "process.marker") for process_id in mocked_processes]
    )
    db.session.commit()
    query = """
    query SubscriptionProcesses($id: UUID!, $search: ResourceSearchInput) {
        subscription(id: $id) {
            processes(search: $search) {
                searchEdges { node { processId } }
            }
        }
    }
    """
    search_filter = {"path": "process.marker", "condition": {"op": "EQ", "value": "hit"}, "valueKind": "STRING"}

    result = _post(
        test_client_graphql,
        query,
        id=generic_subscription_1,
        search={"filters": {"op": "AND", "filters": [search_filter]}},
    )

    assert "errors" not in result
    edges = result["data"]["subscription"]["processes"]["searchEdges"]
    assert sorted(edge["node"]["processId"] for edge in edges) == sorted(str(process_id) for process_id in related)


def test_process_subscriptions_search_is_scoped_to_its_subscriptions(
    test_client_graphql, mocked_processes, generic_subscription_1, generic_subscription_2
):
    """mocked_processes[0] belongs to generic_subscription_1; generic_subscription_2 is indexed but unrelated."""
    db.session.add_all(
        [
            _index_row(EntityType.SUBSCRIPTION, sub_id, "subscription.marker")
            for sub_id in [generic_subscription_1, generic_subscription_2]
        ]
    )
    db.session.commit()
    query = """
    query ProcessSubscriptions($id: UUID!, $search: ResourceSearchInput) {
        process(processId: $id) {
            subscriptions(search: $search) {
                searchEdges { node { subscriptionId } }
            }
        }
    }
    """

    result = _post(test_client_graphql, query, id=str(mocked_processes[0]), search={"filters": HIT_FILTER})

    assert "errors" not in result
    edges = result["data"]["process"]["subscriptions"]["searchEdges"]
    assert [edge["node"]["subscriptionId"] for edge in edges] == [generic_subscription_1]


def test_product_subscriptions_search_is_scoped_to_its_subscriptions(
    test_client_graphql, generic_subscription_1, generic_subscription_2
):
    """generic_subscription_2 is of another product; indexed, it must still stay out of this product's hits."""
    product_id = db.session.get(SubscriptionTable, UUID(generic_subscription_1)).product_id
    db.session.add_all(
        [
            _index_row(EntityType.SUBSCRIPTION, sub_id, "subscription.marker")
            for sub_id in [generic_subscription_1, generic_subscription_2]
        ]
    )
    db.session.commit()
    query = """
    query ProductSubscriptions($filterBy: [GraphqlFilter!], $search: ResourceSearchInput) {
        products(filterBy: $filterBy) {
            page {
                subscriptions(search: $search) {
                    searchEdges { node { subscriptionId } }
                }
            }
        }
    }
    """

    result = _post(
        test_client_graphql,
        query,
        filterBy=[{"field": "productId", "value": str(product_id)}],
        search={"filters": HIT_FILTER},
    )

    assert "errors" not in result
    edges = result["data"]["products"]["page"][0]["subscriptions"]["searchEdges"]
    assert [edge["node"]["subscriptionId"] for edge in edges] == [generic_subscription_1]

# Copyright 2022 SURF.
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
import json
from http import HTTPStatus

import pytest

from test.unit_tests.conftest import do_refresh_subscriptions_search_view


def assert_result_ids_against_expected_ids(result_ids, expected_ids):
    assert sorted(result_ids) == sorted([str(id) for id in expected_ids])


def build_subscriptions_relation_query(body: str) -> str:
    return f"""
query SubscriptionQuery(
    $first: Int!,
    $after: Int!,
    $sortBy: [GraphqlSort!],
    $filterBy: [GraphqlFilter!],
    $query: String,
    $dependsOnFilter: SubscriptionRelationFilter,
    $dependsOnSubscriptionsFilter: [GraphqlFilter!],
    $inUseByFilter: SubscriptionRelationFilter,
    $inUseBySubscriptionsFilter: [GraphqlFilter!],
) {{
    subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy, query: $query)
    {body}
}}
"""


def get_subscriptions_query_with_processes(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query SubscriptionQuery(
    $first: Int!,
    $after: Int!,
    $sortBy: [GraphqlSort!],
    $filterBy: [GraphqlFilter!],
    $query: String,
) {
  subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy, query: $query) {
    page {
      description
      subscriptionId
      status
      insync
      note
      startDate
      endDate
      productBlockInstances {
        ownerSubscriptionId
        inUseByRelations
      }
      processes(sortBy: [{field: "startedAt", order: ASC}]) {
        page {
          processId
          isTask
          lastStep
          lastStatus
          assignee
          failedReason
          traceback
          workflowName
          createdBy
          startedAt
          lastModifiedAt
          product {
            productId
            name
            description
            productType
            status
            tag
            createdAt
            endDate
          }
        }
      }
    }
    pageInfo {
      startCursor
      totalItems
      hasPreviousPage
      endCursor
      hasNextPage
    }
  }
}
    """
    return json.dumps(
        {
            "operationName": "SubscriptionQuery",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
                "query": query_string,
            },
        }
    ).encode("utf-8")


def get_subscriptions_query_with_relations(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
    depends_on_filter: dict[str, str] | None = None,
    depends_on_subscription_filter: dict[str, str] | None = None,
    in_use_by_filter: dict[str, str] | None = None,
    in_use_by_subscription_filter: dict[str, str] | None = None,
) -> bytes:
    query = build_subscriptions_relation_query(
        """{
    page {
      description
      subscriptionId
      status
      insync
      note
      startDate
      endDate
      dependsOnSubscriptions(dependsOnFilter: $dependsOnFilter, first: 20, filterBy: $dependsOnSubscriptionsFilter) {
        page {
          description
          subscriptionId
          status
          insync
          note
          startDate
          endDate
        }
      }
      inUseBySubscriptions(inUseByFilter: $inUseByFilter, first: 20, filterBy: $inUseBySubscriptionsFilter) {
        page {
          description
          subscriptionId
          status
          insync
          note
          startDate
          endDate
        }
      }
    }
    pageInfo {
      startCursor
      totalItems
      hasPreviousPage
      endCursor
      hasNextPage
    }
  }
    """
    )
    return json.dumps(
        {
            "operationName": "SubscriptionQuery",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
                "query": query_string,
                "dependsOnFilter": depends_on_filter,
                "dependsOnSubscriptionsFilter": depends_on_subscription_filter,
                "inUseByFilter": in_use_by_filter,
                "inUseBySubscriptionsFilter": in_use_by_subscription_filter,
            },
        }
    ).encode("utf-8")


@pytest.mark.parametrize(
    "query_args",
    [
        lambda sid: {"filter_by": [{"field": "subscriptionId", "value": sid}]},
        lambda sid: {"query_string": sid},
    ],
)
def test_single_subscription_with_processes(
    fastapi_app_graphql,
    test_client,
    product_type_1_subscriptions_factory,
    mocked_processes,
    mocked_processes_resumeall,  # noqa: F811
    generic_subscription_2,  # noqa: F811
    generic_subscription_1,
    query_args,
):
    # when

    product_type_1_subscriptions_factory(30)
    subscription_id = generic_subscription_1

    do_refresh_subscriptions_search_view()

    data = get_subscriptions_query_with_processes(**query_args(subscription_id))
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["processes"]["page"][0]["processId"] == str(mocked_processes[0])


def test_single_subscription_with_depends_on_subscriptions(
    fastapi_app_graphql,
    test_client,
    product_type_1_subscriptions_factory,
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
):
    # when

    product_type_1_subscriptions_factory(30)

    do_refresh_subscriptions_search_view()

    subscription_id = str(product_sub_list_union_subscription_1)
    data = get_subscriptions_query_with_relations(query_string=subscription_id)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    expected_depends_on_ids = {
        str(subscription.subscription_id) for subscription in [sub_one_subscription_1, sub_two_subscription_1]
    }
    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    depends_on_ids = subscriptions[0]["dependsOnSubscriptions"]["page"]
    result_depends_on_ids = {subscription["subscriptionId"] for subscription in depends_on_ids}
    assert result_depends_on_ids == expected_depends_on_ids
    assert len(subscriptions[0]["inUseBySubscriptions"]["page"]) == 0


def test_single_subscription_with_in_use_by_subscriptions(
    fastapi_app_graphql,
    test_client,
    product_type_1_subscriptions_factory,
    sub_one_subscription_1,
    product_sub_list_union_subscription_1,
):
    # when

    product_type_1_subscriptions_factory(30)

    subscription_id = str(sub_one_subscription_1.subscription_id)
    subscription_query = get_subscriptions_query_with_relations(
        filter_by=[{"field": "subscriptionId", "value": subscription_id}]
    )

    response = test_client.post(
        "/api/graphql", content=subscription_query, headers={"Content-Type": "application/json"}
    )

    expected_in_use_by_ids = [str(product_sub_list_union_subscription_1)]

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert len(subscriptions[0]["dependsOnSubscriptions"]["page"]) == 0
    result_in_use_by_ids = [
        subscription["subscriptionId"] for subscription in subscriptions[0]["inUseBySubscriptions"]["page"]
    ]
    assert result_in_use_by_ids == expected_in_use_by_ids


in_use_by_recurse_all_ids = [
    "subscription_20",
    "subscription_21",
    "subscription_22",
    "subscription_30",
    "subscription_31",
    "subscription_32",
    "subscription_33",
    "subscription_34",
    "subscription_40",
    "subscription_41",
    "subscription_42",
    "subscription_43",
    "subscription_44",
    "subscription_45",
]
in_use_by_recurse_all_with_filter_by_ids = [
    "subscription_22",
    "subscription_32",
]
in_use_by_recurse_status_active_ids = [
    "subscription_20",
    "subscription_22",
    "subscription_30",
    "subscription_32",
    "subscription_34",
    "subscription_40",
    "subscription_43",
    "subscription_45",
]
in_use_by_recurse_depth_limit_ids = [
    "subscription_20",
    "subscription_21",
    "subscription_22",
    "subscription_30",
    "subscription_31",
    "subscription_32",
    "subscription_33",
    "subscription_34",
]
in_use_by_recurse_only_product_type_test_ids = [
    "subscription_20",
    "subscription_21",
    "subscription_22",
    "subscription_30",
    "subscription_31",
    "subscription_32",
    "subscription_33",
    "subscription_40",
    "subscription_41",
    "subscription_42",
    "subscription_44",
]


@pytest.mark.parametrize(
    "in_use_by_filter,in_use_by_subscription_filter,subscription_ids,subscription_statuses",
    [
        (
            {"recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"]},
            None,
            in_use_by_recurse_all_ids,
            {"ACTIVE", "TERMINATED"},
        ),
        (
            {"recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"]},
            [{"field": "product", "value": "TestProductListNestedTypeOne"}],
            in_use_by_recurse_all_with_filter_by_ids,
            {"ACTIVE"},
        ),
        (
            {"statuses": ["active"], "recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"]},
            None,
            in_use_by_recurse_status_active_ids,
            {"ACTIVE"},
        ),
        (
            {"recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"], "recurseDepthLimit": 1},
            None,
            in_use_by_recurse_depth_limit_ids,
            {"ACTIVE", "TERMINATED"},
        ),
        (
            {"recurseProductTypes": ["Test"]},
            None,
            in_use_by_recurse_only_product_type_test_ids,
            {"ACTIVE", "TERMINATED"},
        ),
    ],
    ids=[
        "recurse_all",
        "recurse_all_with_filter_by",
        "recurse_status_active",
        "recurse_depth_limit",
        "recurse_only_product_type_test",
    ],
)
def test_single_subscription_with_in_use_by_subscriptions_recurse(
    fastapi_app_graphql,
    test_client,
    factory_subscription_with_nestings_in_use_by,
    in_use_by_filter,
    in_use_by_subscription_filter,
    subscription_ids,
    subscription_statuses,
):
    # when

    all_ids = factory_subscription_with_nestings_in_use_by

    subscription_id = str(all_ids["subscription_10"])
    subscription_query = get_subscriptions_query_with_relations(
        filter_by=[{"field": "subscriptionId", "value": subscription_id}],
        in_use_by_filter=in_use_by_filter,
        in_use_by_subscription_filter=in_use_by_subscription_filter,
    )

    response = test_client.post(
        "/api/graphql", content=subscription_query, headers={"Content-Type": "application/json"}
    )

    expected_relation_ids = [all_ids[sub_id] for sub_id in subscription_ids]

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]

    assert "errors" not in result
    assert subscriptions[0]["subscriptionId"] == subscription_id
    result_related_ids = [
        subscription["subscriptionId"] for subscription in subscriptions[0]["inUseBySubscriptions"]["page"]
    ]
    assert_result_ids_against_expected_ids(result_related_ids, expected_relation_ids)
    result_related_statuses = {
        subscription["status"] for subscription in subscriptions[0]["inUseBySubscriptions"]["page"]
    }
    assert result_related_statuses == subscription_statuses


depends_on_recurse_all_ids = [
    "subscription_10",
    "subscription_11",
    "subscription_12",
    "subscription_13",
    "subscription_14",
    "subscription_15",
    "subscription_20",
    "subscription_21",
    "subscription_22",
    "subscription_23",
    "subscription_24",
    "subscription_30",
    "subscription_31",
    "subscription_32",
]
depends_on_recurse_all_with_filter_by_ids = [
    "subscription_22",
    "subscription_32",
]
depends_on_recurse_status_active_ids = [
    "subscription_10",
    "subscription_13",
    "subscription_15",
    "subscription_20",
    "subscription_22",
    "subscription_24",
    "subscription_30",
    "subscription_32",
]
depends_on_recurse_depth_limit_ids = [
    "subscription_20",
    "subscription_21",
    "subscription_22",
    "subscription_23",
    "subscription_24",
    "subscription_30",
    "subscription_31",
    "subscription_32",
]
depends_on_recurse_only_product_type_test_ids = [
    "subscription_10",
    "subscription_11",
    "subscription_12",
    "subscription_14",
    "subscription_20",
    "subscription_21",
    "subscription_22",
    "subscription_23",
    "subscription_30",
    "subscription_31",
    "subscription_32",
]


@pytest.mark.parametrize(
    "depends_on_filter,depends_on_subscription_filter,subscription_ids,subscription_statuses",
    [
        (
            {"recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"]},
            None,
            depends_on_recurse_all_ids,
            {"ACTIVE", "TERMINATED"},
        ),
        (
            {"recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"]},
            [{"field": "product", "value": "TestProductListNestedTypeOne"}],
            depends_on_recurse_all_with_filter_by_ids,
            {"ACTIVE"},
        ),
        (
            {"statuses": ["active"], "recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"]},
            None,
            depends_on_recurse_status_active_ids,
            {"ACTIVE"},
        ),
        (
            {"recurseProductTypes": ["Test", "ProductTypeOne", "ProductTypeTwo"], "recurseDepthLimit": 1},
            None,
            depends_on_recurse_depth_limit_ids,
            {"ACTIVE", "TERMINATED"},
        ),
        (
            {"recurseProductTypes": ["Test"]},
            None,
            depends_on_recurse_only_product_type_test_ids,
            {"ACTIVE", "TERMINATED"},
        ),
    ],
    ids=[
        "recurse_all",
        "recurse_all_with_filter_by",
        "recurse_status_active",
        "recurse_depth_limit",
        "recurse_only_product_type_test",
    ],
)
def test_single_subscription_with_depends_on_subscriptions_recurse(
    fastapi_app_graphql,
    test_client,
    factory_subscription_with_nestings_depends_on,
    depends_on_filter,
    depends_on_subscription_filter,
    subscription_ids,
    subscription_statuses,
):
    # when

    all_ids = factory_subscription_with_nestings_depends_on

    subscription_id = str(all_ids["subscription_40"])
    subscription_query = get_subscriptions_query_with_relations(
        filter_by=[{"field": "subscriptionId", "value": subscription_id}],
        depends_on_filter=depends_on_filter,
        depends_on_subscription_filter=depends_on_subscription_filter,
    )

    response = test_client.post(
        "/api/graphql", content=subscription_query, headers={"Content-Type": "application/json"}
    )

    expected_relation_ids = [all_ids[sub_id] for sub_id in subscription_ids]

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]

    assert "errors" not in result
    assert subscriptions[0]["subscriptionId"] == subscription_id
    result_related_ids = [
        subscription["subscriptionId"] for subscription in subscriptions[0]["dependsOnSubscriptions"]["page"]
    ]
    assert_result_ids_against_expected_ids(result_related_ids, expected_relation_ids)
    result_related_statuses = {
        subscription["status"] for subscription in subscriptions[0]["dependsOnSubscriptions"]["page"]
    }
    assert result_related_statuses == subscription_statuses

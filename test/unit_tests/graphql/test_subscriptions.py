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
import datetime
import json
from http import HTTPStatus
from typing import Union

import pytest

from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle

subscription_fields = [
    "endDate",
    "description",
    "subscriptionId",
    "startDate",
    "status",
    "insync",
    "note",
    "product",
    "productBlockInstances",
]
subscription_product_fields = [
    "productId",
    "name",
    "description",
    "productType",
    "status",
    "tag",
    "createdAt",
    "endDate",
]


def get_subscriptions_query(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list, None] = None,
    sort_by: Union[list, None] = None,
) -> bytes:
    query = """
query SubscriptionQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      description
      subscriptionId
      status
      insync
      note
      startDate
      endDate
      productBlockInstances {
        id
        parent
        subscriptionInstanceId
        ownerSubscriptionId
        productBlockInstanceValues
      }
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_query_with_relations(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query SubscriptionQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      description
      subscriptionId
      status
      insync
      note
      startDate
      endDate
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
      dependsOnSubscriptions {
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
      inUseBySubscriptions {
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_product_generic_one(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query SubscriptionQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      ... on GenericProductOneSubscription {
        description
        subscriptionId
        status
        insync
        note
        startDate
        endDate
        pb1 {
          rt1
        }
        pb2 {
          rt2
          rt3
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_product_sub_list_union(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query SubscriptionQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      ... on ProductSubListUnionSubscription {
        description
        subscriptionId
        status
        insync
        note
        startDate
        endDate
        product{
          productType
        }
        testBlock {
          intField
          strField
          listField
          listUnionBlocks {
            ... on SubBlockOneForTestInactive {
              intField
              strField
            }
            ... on SubBlockTwoForTestInactive {
              intField2
            }
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
            },
        }
    ).encode("utf-8")


def test_subscriptions_single_page(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(4)
    data = get_subscriptions_query()
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 6,
        "totalItems": 7,
    }

    for subscription in subscriptions:
        for field in subscription_fields:
            assert field in subscription
        for field in subscription_product_fields:
            assert field in subscription["product"]


def test_subscriptions_has_next_page(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)
    data = get_subscriptions_query()
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 33,
    }

    for subscription in subscriptions:
        for field in subscription_fields:
            assert field in subscription


def test_subscriptions_has_previous_page(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)
    data = get_subscriptions_query(after=1)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert len(subscriptions) == 10

    assert pageinfo == {
        "hasPreviousPage": True,
        "hasNextPage": True,
        "startCursor": 1,
        "endCursor": 10,
        "totalItems": 33,
    }


def test_subscriptions_sorting_asc(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)
    data = get_subscriptions_query(sort_by=[{"field": "startDate", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 33,
    }

    for i in range(0, 8):
        assert subscriptions[i]["startDate"] < subscriptions[i + 1]["startDate"]


def test_subscriptions_sorting_desc(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)
    data = get_subscriptions_query(sort_by=[{"field": "startDate", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 33,
    }

    for i in range(0, 8):
        assert subscriptions[i + 1]["startDate"] < subscriptions[i]["startDate"]


def test_subscriptions_sorting_product_tag_asc(test_client, generic_subscription_1, generic_subscription_2):
    # when

    data = get_subscriptions_query(sort_by=[{"field": "tag", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 4,
        "totalItems": 5,
    }

    product_tag_list = [subscription["product"]["tag"] for subscription in subscriptions]
    assert product_tag_list == ["GEN1", "GEN2", "Sub", "Sub", "UnionSub"]


def test_subscriptions_sorting_product_tag_desc(test_client, generic_subscription_1, generic_subscription_2):
    # when

    data = get_subscriptions_query(sort_by=[{"field": "tag", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 4,
        "totalItems": 5,
    }

    product_tag_list = [subscription["product"]["tag"] for subscription in subscriptions]
    assert product_tag_list == ["UnionSub", "Sub", "Sub", "GEN2", "GEN1"]


def test_subscriptions_sorting_invalid_field(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)
    data = get_subscriptions_query(sort_by=[{"field": "start_date", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    pageinfo = subscriptions_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 33,
    }

    assert "errors" in result
    assert result["errors"] == [
        {
            "message": "Invalid sort arguments",
            "path": [None, "subscriptions", "Query"],
            "extensions": {
                "invalid_sorting": [{"field": "start_date", "order": "DESC"}],
                "valid_sort_keys": [
                    "productId",
                    "name",
                    "description",
                    "productType",
                    "tag",
                    "status",
                    "createdAt",
                    "endDate",
                    "subscriptionId",
                    "customerId",
                    "insync",
                    "startDate",
                    "note",
                ],
            },
        }
    ]


def test_subscriptions_sorting_invalid_order(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)
    data = get_subscriptions_query(sort_by=[{"field": "start_date", "order": "test"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()

    assert not result["data"]
    assert "errors" in result
    assert "Value 'test' does not exist in 'SortOrder'" in result["errors"][0]["message"]


def test_subscriptions_filtering_on_status(test_client, product_type_1_subscriptions_factory, generic_product_type_1):
    # when

    subscription_ids = product_type_1_subscriptions_factory(30)

    GenericProductOneInactive, GenericProductOne = generic_product_type_1
    subscription_1 = GenericProductOne.from_subscription(subscription_ids[0])
    subscription_1 = subscription_1.from_other_lifecycle(subscription_1, SubscriptionLifecycle.TERMINATED)
    subscription_1.save()
    subscription_9 = GenericProductOne.from_subscription(subscription_ids[8])
    subscription_9 = subscription_9.from_other_lifecycle(subscription_9, SubscriptionLifecycle.TERMINATED)
    subscription_9.save()

    data = get_subscriptions_query(filter_by=[{"field": "status", "value": SubscriptionLifecycle.TERMINATED}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 2,
    }

    result_subscription_ids = [subscription["subscriptionId"] for subscription in subscriptions].sort()
    assert result_subscription_ids == [str(subscription_1.subscription_id), str(subscription_9.subscription_id)].sort()
    assert subscriptions[0]["status"] == "TERMINATED"
    assert subscriptions[1]["status"] == "TERMINATED"


def test_subscriptions_range_filtering_on_start_date(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)

    data = get_subscriptions_query(first=1, filter_by=[{"field": "startDate", "value": "2023-05-24"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    first_subscription = response.json()["data"]["subscriptions"]["page"][0]

    first_subscription_date = datetime.datetime.fromisoformat(first_subscription["startDate"])
    higher_then_date = first_subscription_date.isoformat()
    lower_then_date = (first_subscription_date + datetime.timedelta(days=3)).isoformat()

    data = get_subscriptions_query(
        filter_by=[
            {"field": "startDateGte", "value": higher_then_date},
            {"field": "startDateLte", "value": lower_then_date},
        ]
    )
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 3,
        "totalItems": 4,
    }

    for subscription in subscriptions:
        assert higher_then_date <= subscription["startDate"] <= lower_then_date


def test_subscriptions_filtering_with_invalid_filter(
    test_client, product_type_1_subscriptions_factory, generic_product_type_1
):
    # when

    subscription_ids = product_type_1_subscriptions_factory(30)

    GenericProductOneInactive, GenericProductOne = generic_product_type_1
    subscription_1 = GenericProductOne.from_subscription(subscription_ids[0])
    subscription_1 = subscription_1.from_other_lifecycle(subscription_1, SubscriptionLifecycle.TERMINATED)
    subscription_1.save()
    subscription_9 = GenericProductOne.from_subscription(subscription_ids[8])
    subscription_9 = subscription_9.from_other_lifecycle(subscription_9, SubscriptionLifecycle.TERMINATED)
    subscription_9.save()

    data = get_subscriptions_query(
        filter_by=[
            {"field": "status", "value": SubscriptionLifecycle.TERMINATED},
            {"field": "test", "value": "invalid"},
        ]
    )
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    errors = result["errors"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert errors == [
        {
            "message": "Invalid filter arguments",
            "path": [None, "subscriptions", "Query"],
            "extensions": {
                "invalid_filters": [{"field": "test", "value": "invalid"}],
                "valid_filter_keys": [
                    "subscriptionId",
                    "subscriptionIds",
                    "description",
                    "status",
                    "product",
                    "insync",
                    "note",
                    "statuses",
                    "tags",
                    "tag",
                    "tsv",
                    "startDate",
                    "endDate",
                    "startDateGt",
                    "startDateGte",
                    "startDateLt",
                    "startDateLte",
                    "startDateNe",
                    "endDateGt",
                    "endDateGte",
                    "endDateLt",
                    "endDateLte",
                    "endDateNe",
                ],
            },
        }
    ]
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 2,
    }

    for subscription in subscriptions:
        assert subscription["status"] == "TERMINATED"


def test_single_subscription(test_client, product_type_1_subscriptions_factory, generic_product_type_1):
    # when

    _, GenericProductOne = generic_product_type_1
    subscription_ids = product_type_1_subscriptions_factory(30)
    subscription_id = subscription_ids[10]
    data = get_subscriptions_query(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    subscription = GenericProductOne.from_subscription(subscription_id)

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
    assert subscriptions[0]["productBlockInstances"] == [
        {
            "id": 0,
            "subscriptionInstanceId": str(subscription.pb_1.subscription_instance_id),
            "ownerSubscriptionId": subscription_id,
            "parent": None,
            "productBlockInstanceValues": [
                {"field": "name", "value": "PB_1"},
                {"field": "label", "value": None},
                {"field": "rt1", "value": "Value1"},
            ],
        },
        {
            "id": 1,
            "subscriptionInstanceId": str(subscription.pb_2.subscription_instance_id),
            "ownerSubscriptionId": subscription_id,
            "parent": None,
            "productBlockInstanceValues": [
                {"field": "name", "value": "PB_2"},
                {"field": "label", "value": None},
                {"field": "rt2", "value": 42},
                {"field": "rt3", "value": "Value2"},
            ],
        },
    ]


def test_single_subscription_with_processes(
    fastapi_app_graphql,
    test_client,
    product_type_1_subscriptions_factory,
    mocked_processes,
    mocked_processes_resumeall,  # noqa: F811
    generic_subscription_2,  # noqa: F811
    generic_subscription_1,
):
    # when

    product_type_1_subscriptions_factory(30)
    subscription_id = generic_subscription_1
    data = get_subscriptions_query_with_relations(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
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
    subscription_id = str(product_sub_list_union_subscription_1)
    data = get_subscriptions_query_with_relations(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    expected_depends_on_ids = [
        str(subscription.subscription_id) for subscription in [sub_one_subscription_1, sub_two_subscription_1]
    ].sort()
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
    assert len(subscriptions[0]["processes"]["page"]) == 0
    result_depends_on_ids = [
        subscription["subscriptionId"] for subscription in subscriptions[0]["dependsOnSubscriptions"]["page"]
    ].sort()
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
    data = get_subscriptions_query_with_relations(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

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
    assert len(subscriptions[0]["processes"]["page"]) == 0
    assert len(subscriptions[0]["dependsOnSubscriptions"]["page"]) == 0
    result_in_use_by_ids = [
        subscription["subscriptionId"] for subscription in subscriptions[0]["inUseBySubscriptions"]["page"]
    ]
    assert result_in_use_by_ids == expected_in_use_by_ids


def expect_fail_test_if_too_many_duplicate_types_in_interface(result):
    if "errors" in result and "are you using a strawberry.field" in result["errors"][0]["message"]:
        pytest.xfail("Test fails when executed with all tests")


def test_subscriptions_product_generic_one(
    fastapi_app_graphql,
    test_client,
    product_type_1_subscriptions_factory,
):
    # when

    subscriptions = product_type_1_subscriptions_factory(30)
    subscription_id = str(subscriptions[0])
    data = get_subscriptions_product_generic_one(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    expect_fail_test_if_too_many_duplicate_types_in_interface(result)

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["pb1"] == {"rt1": "Value1"}
    assert subscriptions[0]["pb2"] == {"rt2": 42, "rt3": "Value2"}


def test_single_subscription_product_list_union_type(
    fastapi_app_graphql,
    test_client,
    product_sub_list_union_subscription_1,
):
    # when

    subscription_id = str(product_sub_list_union_subscription_1)
    data = get_subscriptions_product_sub_list_union(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    expect_fail_test_if_too_many_duplicate_types_in_interface(result)

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["testBlock"] == {
        "intField": 1,
        "strField": "blah",
        "listField": [2],
        "listUnionBlocks": [{"intField2": 3}, {"intField": 1, "strField": "blah"}],
    }


def test_single_subscription_product_list_union_type_provisioning_subscription(
    fastapi_app_graphql,
    test_client,
    product_sub_list_union_subscription_1,
):
    # when

    subscription = SubscriptionModel.from_subscription(product_sub_list_union_subscription_1)
    subscription = subscription.from_other_lifecycle(subscription, SubscriptionLifecycle.PROVISIONING)
    subscription.save()

    subscription_id = str(product_sub_list_union_subscription_1)
    data = get_subscriptions_product_sub_list_union(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    expect_fail_test_if_too_many_duplicate_types_in_interface(result)

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["testBlock"] == {
        "intField": 1,
        "strField": "blah",
        "listField": [2],
        "listUnionBlocks": [{"intField2": 3}, {"intField": 1, "strField": "blah"}],
    }


def test_single_subscription_product_list_union_type_terminated_subscription(
    fastapi_app_graphql,
    test_client,
    product_sub_list_union_subscription_1,
):
    # when

    subscription = SubscriptionModel.from_subscription(product_sub_list_union_subscription_1)
    subscription = subscription.from_other_lifecycle(subscription, SubscriptionLifecycle.TERMINATED)
    subscription.save()

    subscription_id = str(product_sub_list_union_subscription_1)
    data = get_subscriptions_product_sub_list_union(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    expect_fail_test_if_too_many_duplicate_types_in_interface(result)

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["testBlock"] == {
        "intField": 1,
        "strField": "blah",
        "listField": [2],
        "listUnionBlocks": [{"intField2": 3}, {"intField": 1, "strField": "blah"}],
    }

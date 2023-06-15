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

from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.api.test_subscriptions import PORT_A_SUBSCRIPTION_ID, SERVICE_SUBSCRIPTION_ID, seed  # noqa: F401

subscription_fields = [
    "endDate",
    "description",
    "subscriptionId",
    "startDate",
    "productId",
    "status",
    "tag",
    "insync",
    "name",
    "note",
]


def get_subscriptions_query(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query SubscriptionQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      endDate
      description
      subscriptionId
      startDate
      productId
      status
      tag
      insync
      name
      note
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
      endDate
      description
      subscriptionId
      startDate
      productId
      status
      tag
      insync
      name
      note
      processes {
        page {
          assignee
          createdBy
          failedReason
          isTask
          lastStep
          traceback
          id
          lastModified
          started
          workflowName
          status
          step
          product
        }
      }
      dependsOnSubscriptions {
        page {
          name
          insync
          endDate
          description
          productId
          startDate
          status
          subscriptionId
          tag
          note
        }
      }
      inUseBySubscriptions {
        page {
          name
          insync
          endDate
          description
          productId
          startDate
          status
          subscriptionId
          tag
          note
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


def test_subscriptions_single_page(test_client, generic_subscriptions_factory):
    # when

    generic_subscriptions_factory(7)
    data = get_subscriptions_query()
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 6,
        "totalItems": "7",
    }

    for subscription in subscriptions:
        for field in subscription_fields:
            assert field in subscription


def test_subscriptions_has_next_page(test_client, generic_subscriptions_factory):
    # when

    generic_subscriptions_factory(30)
    data = get_subscriptions_query()
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": "30",
    }

    for subscription in subscriptions:
        for field in subscription_fields:
            assert field in subscription


def test_subscriptions_has_previous_page(test_client, generic_subscriptions_factory):
    # when

    generic_subscriptions_factory(30)
    data = get_subscriptions_query(after=1)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 10

    assert pageinfo == {
        "hasPreviousPage": True,
        "hasNextPage": True,
        "startCursor": 1,
        "endCursor": 10,
        "totalItems": "30",
    }


def test_subscriptions_sorting_asc(test_client, generic_subscriptions_factory):
    # when

    generic_subscriptions_factory(30)
    data = get_subscriptions_query(sort_by=[{"field": "start_date", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": "30",
    }

    for i in range(0, 8):
        assert subscriptions[i]["startDate"] < subscriptions[i + 1]["startDate"]


def test_subscriptions_sorting_desc(test_client, generic_subscriptions_factory):
    # when

    generic_subscriptions_factory(30)
    data = get_subscriptions_query(sort_by=[{"field": "start_date", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": "30",
    }

    for i in range(0, 8):
        assert subscriptions[i + 1]["startDate"] < subscriptions[i]["startDate"]


def test_subscriptions_filtering_on_status(test_client, generic_subscriptions_factory, generic_product_type_1):
    # when

    subscription_ids = generic_subscriptions_factory(30)

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

    # then

    assert HTTPStatus.OK == response.status_code

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": "2",
    }

    assert subscriptions[0]["subscriptionId"] == str(subscription_1.subscription_id)
    assert subscriptions[0]["status"] == SubscriptionLifecycle.TERMINATED
    assert subscriptions[1]["subscriptionId"] == str(subscription_9.subscription_id)
    assert subscriptions[1]["status"] == SubscriptionLifecycle.TERMINATED


def test_subscriptions_range_filtering_on_start_date(test_client, generic_subscriptions_factory):
    # when

    generic_subscriptions_factory(30)
    higher_then_date = datetime.datetime.now().isoformat()
    lower_then_date = (datetime.datetime.now() + datetime.timedelta(days=3)).isoformat()

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

    # then

    assert HTTPStatus.OK == response.status_code

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 2,
        "totalItems": "3",
    }

    for subscription in subscriptions:
        assert higher_then_date < subscription["startDate"] < lower_then_date


def test_subscriptions_filtering_with_invalid_filter(
    test_client, generic_subscriptions_factory, generic_product_type_1
):
    # when

    subscription_ids = generic_subscriptions_factory(30)

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
        "totalItems": "2",
    }

    for subscription in subscriptions:
        assert subscription["status"] == SubscriptionLifecycle.TERMINATED


def test_single_subscription(test_client, generic_subscriptions_factory):
    # when

    subscription_ids = generic_subscriptions_factory(30)
    subscription_id = subscription_ids[10]
    data = get_subscriptions_query(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": "1",
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id


def test_single_subscription_with_processes(
    test_client,
    generic_subscriptions_factory,
    mocked_processes,
    mocked_processes_resumeall,  # noqa: F811
    generic_subscription_2,  # noqa: F811
    generic_subscription_1,
):
    # when

    generic_subscriptions_factory(30)
    subscription_id = generic_subscription_1
    data = get_subscriptions_query_with_relations(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": "1",
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["processes"]["page"][0]["id"] == str(mocked_processes[0])


def test_single_subscription_with_depends_on_subscriptions(
    test_client, generic_subscriptions_factory, seed  # noqa: F811
):
    # when

    generic_subscriptions_factory(30)
    subscription_id = SERVICE_SUBSCRIPTION_ID
    data = get_subscriptions_query_with_relations(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": "1",
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert len(subscriptions[0]["processes"]["page"]) == 0
    assert subscriptions[0]["dependsOnSubscriptions"]["page"][0]["subscriptionId"] == PORT_A_SUBSCRIPTION_ID
    assert len(subscriptions[0]["inUseBySubscriptions"]["page"]) == 0


def test_single_subscription_with_in_use_by_subscriptions(
    test_client, generic_subscriptions_factory, seed  # noqa: F811
):
    # when

    generic_subscriptions_factory(30)
    subscription_id = PORT_A_SUBSCRIPTION_ID
    data = get_subscriptions_query_with_relations(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert len(subscriptions) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": "1",
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert len(subscriptions[0]["processes"]["page"]) == 0
    assert len(subscriptions[0]["dependsOnSubscriptions"]["page"]) == 0
    assert subscriptions[0]["inUseBySubscriptions"]["page"][0]["subscriptionId"] == SERVICE_SUBSCRIPTION_ID

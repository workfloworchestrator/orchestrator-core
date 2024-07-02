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

import pytest
from sqlalchemy import select

from orchestrator.db import SubscriptionMetadataTable, db
from orchestrator.db.models import SubscriptionCustomerDescriptionTable, SubscriptionTable
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.conftest import do_refresh_subscriptions_search_view

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
CUSTOMER_ID = "a6274018-0580-41cd-9fe8-17b946706e9f"


def build_subscriptions_query(body: str) -> str:
    return f"""
query SubscriptionQuery(
    $first: Int!,
    $after: Int!,
    $sortBy: [GraphqlSort!],
    $filterBy: [GraphqlFilter!],
    $query: String
) {{
    subscriptions(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy, query: $query)
    {body}
}}
"""


def get_subscriptions_query(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict] | None = None,
    sort_by: list | None = None,
    query_string: str | None = None,
) -> bytes:
    gql_query = build_subscriptions_query(
        """{
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
        inUseByRelations
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
      customerDescriptions {
        subscriptionId
        customerId
        description
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
            "query": gql_query,
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
) -> bytes:
    query = build_subscriptions_query(
        """{
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_product_block_json_schema_query(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = build_subscriptions_query(
        """{
    page {
      _schema
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_product_generic_one(
    first: int = 10,
    after: int = 0,
    filter_by: list[str] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = build_subscriptions_query(
        """{
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
        customerDescriptions {
            subscriptionId
            customerId
            description
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_product_sub_list_union(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[str] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = build_subscriptions_query(
        """{
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_with_metadata_and_schema_query(
    first: int = 1,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    gql_query = build_subscriptions_query(
        """{
    page {
      subscriptionId
      metadata
      _metadataSchema
    }
  }
    """
    )
    return json.dumps(
        {
            "operationName": "SubscriptionQuery",
            "query": gql_query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
                "query": query_string,
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
    assert "errors" not in result

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

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
    assert "errors" not in result

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

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
    assert "errors" not in result

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

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
    assert "errors" not in result

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

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
    assert "errors" not in result

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

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
    assert "errors" not in result

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

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
    assert "errors" not in result

    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

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
            "message": (
                "Invalid sort arguments (invalid_sorting=['start_date'] "
                "valid_sort_keys=['customerId', 'description', 'endDate', "
                "'insync', 'note', 'productCreatedAt', 'productDescription', "
                "'productEndDate', 'productId', 'productName', 'productStatus', "
                "'productTag', 'productType', 'startDate', 'status', "
                "'subscriptionId', 'tag'])"
            ),
            "path": ["subscriptions"],
            "extensions": {"error_type": "internal_error"},
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


@pytest.mark.parametrize(
    "query_args",
    [
        {"filter_by": [{"field": "status", "value": SubscriptionLifecycle.TERMINATED}]},
        {"query_string": "status:terminated"},
    ],
)
def test_subscriptions_filtering_on_status(
    test_client, product_type_1_subscriptions_factory, generic_product_type_1, query_args
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
    do_refresh_subscriptions_search_view()

    subscription_query = get_subscriptions_query(**query_args)

    response = test_client.post(
        "/api/graphql", content=subscription_query, headers={"Content-Type": "application/json"}
    )

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

    result_subscription_ids = {subscription["subscriptionId"] for subscription in subscriptions}
    assert result_subscription_ids == {str(subscription_1.subscription_id), str(subscription_9.subscription_id)}
    assert subscriptions[0]["status"] == "TERMINATED"
    assert subscriptions[1]["status"] == "TERMINATED"


def test_subscriptions_range_filtering_on_start_date(test_client, product_type_1_subscriptions_factory):
    # when

    product_type_1_subscriptions_factory(30)

    data = get_subscriptions_query(first=1, filter_by=[{"field": "startDate", "value": "2023-05-24"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    first_subscription = response.json()["data"]["subscriptions"]["page"][0]

    first_subscription_date = datetime.datetime.fromisoformat(first_subscription["startDate"])
    higher_than_date = first_subscription_date.isoformat()
    lower_than_date = (first_subscription_date + datetime.timedelta(days=3)).isoformat()

    data = get_subscriptions_query(
        filter_by=[
            {"field": "startDate", "value": f">={higher_than_date}"},
            {"field": "startDate", "value": f"<={lower_than_date}"},
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
        assert higher_than_date <= subscription["startDate"] <= lower_than_date


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
            "message": (
                "Invalid filter arguments (invalid_filters=['test'] "
                "valid_filter_keys=['customerId', 'description', 'endDate', 'insync', "
                "'note', 'product', 'productId', 'startDate', 'status', 'subscriptionId', 'tag'])"
            ),
            "path": ["subscriptions"],
            "extensions": {"error_type": "internal_error"},
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


@pytest.mark.parametrize(
    "query_args",
    [
        lambda sid: {"filter_by": [{"field": "subscriptionId", "value": sid}]},
        lambda sid: {"query_string": f"subscription_id:{sid}"},
        lambda sid: {"query_string": f"subscriptionId:{sid}"},
        lambda sid: {"query_string": f"{sid}"},
        lambda sid: {"query_string": f"{sid.split('-')[0]}"},
        lambda sid: {"filter_by": [{"field": "customerId", "value": CUSTOMER_ID.split("-")[0]}]},
        lambda sid: {"query_string": CUSTOMER_ID.split("-")[0]},
    ],
)
def test_single_subscription(test_client, product_type_1_subscriptions_factory, generic_product_type_1, query_args):
    # given

    _, GenericProductOne = generic_product_type_1
    subscription_ids = product_type_1_subscriptions_factory(30)

    do_refresh_subscriptions_search_view()

    subscription_id = subscription_ids[10]
    subscription = db.session.execute(
        select(SubscriptionTable).filter(SubscriptionTable.subscription_id == subscription_id)
    ).scalar_one_or_none()
    subscription.customer_id = CUSTOMER_ID
    subscription.customer_descriptions = [
        SubscriptionCustomerDescriptionTable(
            subscription_id=subscription_id, customer_id=CUSTOMER_ID, description="customer alias"
        )
    ]
    db.session.add(subscription)
    db.session.commit()

    do_refresh_subscriptions_search_view()

    # when
    data = get_subscriptions_query(**query_args(subscription_id))
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
    assert subscriptions[0]["status"] == SubscriptionLifecycle.ACTIVE.name
    assert subscriptions[0]["customerDescriptions"] == [
        {
            "subscriptionId": subscription_id,
            "customerId": "a6274018-0580-41cd-9fe8-17b946706e9f",
            "description": "customer alias",
        }
    ]
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
            "inUseByRelations": [],
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
            "inUseByRelations": [],
        },
    ]


@pytest.mark.parametrize(
    "query_args,total_items",
    [
        (lambda ids: {}, 33),
        (lambda ids: {"filter_by": [{"field": "subscriptionId", "value": f"{ids[0]}|{ids[1]}"}]}, 2),
        (lambda ids: {"filter_by": [{"field": "subscriptionId", "value": "|".join(ids[3:8])}]}, 5),
        (lambda ids: {"query_string": f"subscriptionId:({ids[2]}|{ids[3]})"}, 2),
    ],
)
def test_multiple_subscriptions(
    test_client, product_type_1_subscriptions_factory, generic_product_type_1, query_args, total_items
):
    # given

    _, GenericProductOne = generic_product_type_1
    subscription_ids = product_type_1_subscriptions_factory(30)

    do_refresh_subscriptions_search_view()

    # when
    data = get_subscriptions_query(first=100, **query_args(subscription_ids))
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]
    pageinfo = subscriptions_data["pageInfo"]

    assert "errors" not in result
    assert len(subscriptions) == total_items
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": total_items - 1,
        "totalItems": total_items,
    }


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

    data = get_subscriptions_query_with_relations(**query_args(subscription_id))
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
    assert len(subscriptions[0]["processes"]["page"]) == 0
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
    assert len(subscriptions[0]["processes"]["page"]) == 0
    assert len(subscriptions[0]["dependsOnSubscriptions"]["page"]) == 0
    result_in_use_by_ids = [
        subscription["subscriptionId"] for subscription in subscriptions[0]["inUseBySubscriptions"]["page"]
    ]
    assert result_in_use_by_ids == expected_in_use_by_ids

    list_sub = SubscriptionModel.from_subscription(product_sub_list_union_subscription_1)
    assert subscriptions[0]["productBlockInstances"] == [
        {
            "ownerSubscriptionId": subscription_id,
            "inUseByRelations": [
                {
                    "subscription_id": str(product_sub_list_union_subscription_1),
                    "subscription_instance_id": str(list_sub.test_block.subscription_instance_id),
                }
            ],
        }
    ]


def test_single_subscription_schema(
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
    data = get_subscriptions_product_block_json_schema_query(
        filter_by=[{"field": "subscriptionId", "value": subscription_id}]
    )
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]

    assert "errors" not in result
    expected = {
        "$defs": {
            "ProductBlockWithListUnionForTestInactive": {
                "description": "Valid for statuses: all others\n\nSee `active` version.",
                "properties": {
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Name"},
                    "subscription_instance_id": {
                        "format": "uuid",
                        "title": "Subscription Instance Id",
                        "type": "string",
                    },
                    "owner_subscription_id": {"format": "uuid", "title": "Owner Subscription Id", "type": "string"},
                    "label": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None, "title": "Label"},
                    "list_union_blocks": {
                        "items": {
                            "anyOf": [
                                {"$ref": "#/$defs/SubBlockTwoForTestInactive"},
                                {"$ref": "#/$defs/SubBlockOneForTestInactive"},
                            ]
                        },
                        "title": "List Union Blocks",
                        "type": "array",
                    },
                    "int_field": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                        "title": "Int Field",
                    },
                    "str_field": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Str Field",
                    },
                    "list_field": {"items": {"type": "integer"}, "title": "List Field", "type": "array"},
                },
                "required": ["name", "subscription_instance_id", "owner_subscription_id", "list_union_blocks"],
                "title": "ProductBlockWithListUnionForTestInactive",
                "type": "object",
            },
            "ProductLifecycle": {
                "enum": ["active", "pre production", "phase out", "end of life"],
                "title": "ProductLifecycle",
                "type": "string",
            },
            "ProductModel": {
                "description": "Represent the product as defined in the database as a dataclass.",
                "properties": {
                    "product_id": {"format": "uuid", "title": "Product Id", "type": "string"},
                    "name": {"title": "Name", "type": "string"},
                    "description": {"title": "Description", "type": "string"},
                    "product_type": {"title": "Product Type", "type": "string"},
                    "tag": {"title": "Tag", "type": "string"},
                    "status": {"$ref": "#/$defs/ProductLifecycle"},
                    "created_at": {
                        "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Created At",
                    },
                    "end_date": {
                        "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "End Date",
                    },
                },
                "required": ["product_id", "name", "description", "product_type", "tag", "status"],
                "title": "ProductModel",
                "type": "object",
            },
            "SubBlockOneForTestInactive": {
                "description": "Valid for statuses: all others\n\nSee `active` version.",
                "properties": {
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Name"},
                    "subscription_instance_id": {
                        "format": "uuid",
                        "title": "Subscription Instance Id",
                        "type": "string",
                    },
                    "owner_subscription_id": {"format": "uuid", "title": "Owner Subscription Id", "type": "string"},
                    "label": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None, "title": "Label"},
                    "int_field": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                        "title": "Int Field",
                    },
                    "str_field": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Str Field",
                    },
                },
                "required": ["name", "subscription_instance_id", "owner_subscription_id"],
                "title": "SubBlockOneForTestInactive",
                "type": "object",
            },
            "SubBlockTwoForTestInactive": {
                "description": "Valid for statuses: all others\n\nSee `active` version.",
                "properties": {
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Name"},
                    "subscription_instance_id": {
                        "format": "uuid",
                        "title": "Subscription Instance Id",
                        "type": "string",
                    },
                    "owner_subscription_id": {"format": "uuid", "title": "Owner Subscription Id", "type": "string"},
                    "label": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None, "title": "Label"},
                    "int_field_2": {"title": "Int Field 2", "type": "integer"},
                },
                "required": ["name", "subscription_instance_id", "owner_subscription_id", "int_field_2"],
                "title": "SubBlockTwoForTestInactive",
                "type": "object",
            },
            "SubscriptionLifecycle": {
                "enum": ["initial", "active", "migrating", "disabled", "terminated", "provisioning"],
                "title": "SubscriptionLifecycle",
                "type": "string",
            },
        },
        "description": "Valid for statuses: all others\n\nSee `active` version.",
        "properties": {
            "product": {"$ref": "#/$defs/ProductModel"},
            "customer_id": {"title": "Customer Id", "type": "string"},
            "subscription_id": {"format": "uuid", "title": "Subscription Id", "type": "string"},
            "description": {"default": "Initial subscription", "title": "Description", "type": "string"},
            "status": {"allOf": [{"$ref": "#/$defs/SubscriptionLifecycle"}], "default": "initial"},
            "insync": {"default": False, "title": "Insync", "type": "boolean"},
            "start_date": {
                "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                "default": None,
                "title": "Start Date",
            },
            "end_date": {
                "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                "default": None,
                "title": "End Date",
            },
            "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None, "title": "Note"},
            "test_block": {"anyOf": [{"$ref": "#/$defs/ProductBlockWithListUnionForTestInactive"}, {"type": "null"}]},
        },
        "required": ["product", "customer_id", "test_block"],
        "title": "ProductSubListUnionInactive",
        "type": "object",
    }
    actual = subscriptions[0]["_schema"]
    assert actual == expected


def test_single_subscription_metadata_and_schema(
    fastapi_app_graphql,
    test_client,
    sub_one_subscription_1,
):
    # when
    expected_metadata = {"some_metadata_prop": ["test value 1", "test 2"]}
    subscription_id = str(sub_one_subscription_1.subscription_id)
    subscription_metadata = SubscriptionMetadataTable(subscription_id=subscription_id, metadata_=expected_metadata)
    db.session.add(subscription_metadata)
    db.session.commit()

    data = get_subscriptions_with_metadata_and_schema_query(
        filter_by=[{"field": "subscriptionId", "value": subscription_id}]
    )
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    subscriptions_data = result["data"]["subscriptions"]
    subscriptions = subscriptions_data["page"]

    assert "errors" not in result
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["metadata"] == expected_metadata
    assert subscriptions[0]["_metadataSchema"] == {
        "title": "Metadata",
        "type": "object",
        "properties": {
            "some_metadata_prop": {"title": "Some Metadata Prop", "type": "array", "items": {"type": "string"}}
        },
        "required": ["some_metadata_prop"],
    }


def test_subscriptions_product_generic_one(
    fastapi_app_graphql,
    test_client,
    product_type_1_subscriptions_factory,
):
    # when

    subscriptions = product_type_1_subscriptions_factory(30)
    subscription_id = str(subscriptions[0])
    subscription = db.session.execute(
        select(SubscriptionTable).filter(SubscriptionTable.subscription_id == subscription_id)
    ).scalar_one_or_none()
    subscription.customer_descriptions = [
        SubscriptionCustomerDescriptionTable(customer_id=CUSTOMER_ID, description="customer alias")
    ]
    db.session.add(subscription)
    db.session.commit()

    data = get_subscriptions_product_generic_one(filter_by=[{"field": "subscriptionId", "value": subscription_id}])
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
        "totalItems": 1,
    }
    assert subscriptions[0]["subscriptionId"] == subscription_id
    assert subscriptions[0]["status"] == SubscriptionLifecycle.ACTIVE.name
    assert subscriptions[0]["pb1"] == {"rt1": "Value1"}
    assert subscriptions[0]["pb2"] == {"rt2": 42, "rt3": "Value2"}
    assert subscriptions[0]["customerDescriptions"] == [
        {
            "subscriptionId": subscription_id,
            "customerId": "a6274018-0580-41cd-9fe8-17b946706e9f",
            "description": "customer alias",
        }
    ]


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
    assert subscriptions[0]["status"] == SubscriptionLifecycle.ACTIVE.name
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

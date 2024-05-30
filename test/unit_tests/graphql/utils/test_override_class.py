import json
from http import HTTPStatus
from uuid import UUID

import pytest
import strawberry

from orchestrator.graphql.schemas.customer import CustomerType
from orchestrator.graphql.utils.override_class import override_class
from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


@pytest.fixture
def override_class_app_graphql(
    fastapi_app_graphql,
    test_client,
    sub_one_subscription_1,
):
    def customer_id_override(self) -> str:
        return "overriden"

    customer_id_override_field = strawberry.field(resolver=customer_id_override, description="Returns customer_id")
    customer_id_override_field.name = "customer_id"

    def new(self) -> UUID:
        return self.customer_id

    new_field = strawberry.field(resolver=new, description="Returns new_field")
    new_field.name = "new_field"

    override_class(CustomerType, [customer_id_override_field, new_field])

    fastapi_app_graphql.register_graphql()
    yield fastapi_app_graphql

    # reset the overriden fields.

    @strawberry.field(description="Returns customer_id")  # type: ignore
    def customer_id(self) -> str:
        return self.customer_id

    customer_id.name = "customer_id"

    override_class(CustomerType, [customer_id])
    CustomerType.__strawberry_definition__.fields = [
        field for field in CustomerType.__strawberry_definition__.fields if field.name != "new_field"
    ]
    fastapi_app_graphql.register_graphql()


def get_customers_query(
    first: int = 1,
    after: int = 0,
    filter_by: list[str] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    override_fields: bool = False,
) -> bytes:
    query = """
query CustomerQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {{
  customers(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {{
    page {{
      customerId
      fullname
      shortcode
        {}
    }}
  }}
}}
    """.format(
        "newField" if override_fields else "",
    )
    return json.dumps(
        {
            "operationName": "CustomerQuery",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
            },
        }
    ).encode("utf-8")


def get_subscriptions_customer_query(
    first: int = 1,
    after: int = 0,
    filter_by: list[str] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    override_fields: bool = False,
) -> bytes:
    query = """
query SubscriptionQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {{
  subscriptions(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {{
    page {{
      customer {{
        customerId
        fullname
        shortcode
        {}
      }}
    }}
  }}
}}
    """.format(
        "newField" if override_fields else "",
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
            },
        }
    ).encode("utf-8")


def get_subscriptions_detail_customer_query(
    first: int = 1,
    after: int = 0,
    filter_by: list[str] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    override_fields: bool = False,
) -> bytes:
    query = """
query SubscriptionQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {{
  subscriptions(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {{
    page {{
      ... on ProductSubOneSubscription {{
        customer {{
          customerId
          fullname
          shortcode
          {}
        }}
      }}
    }}
  }}
}}
    """.format(
        "newField" if override_fields else "",
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
            },
        }
    ).encode("utf-8")


def test_customers(fastapi_app_graphql, test_client):
    # when
    response = test_client.post(GRAPHQL_ENDPOINT, content=get_customers_query(), headers=GRAPHQL_HEADERS)

    # then
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]["page"][0]
    assert customer_data == {
        "customerId": "59289a57-70fb-4ff5-9c93-10fe67b12434",
        "fullname": "Default::Orchestrator-Core Customer",
        "shortcode": "default-cust",
    }


def test_customers_overriden(override_class_app_graphql, test_client):
    # when
    response = test_client.post(
        GRAPHQL_ENDPOINT, content=get_customers_query(override_fields=True), headers=GRAPHQL_HEADERS
    )

    # then
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]["page"][0]
    assert customer_data == {
        "customerId": "overriden",
        "fullname": "Default::Orchestrator-Core Customer",
        "shortcode": "default-cust",
        "newField": "59289a57-70fb-4ff5-9c93-10fe67b12434",
    }


def test_subscription_customer(fastapi_app_graphql, test_client, sub_one_subscription_1):
    # when
    response = test_client.post(
        GRAPHQL_ENDPOINT,
        content=get_subscriptions_customer_query(
            filter_by=[{"field": "subscriptionId", "value": str(sub_one_subscription_1.subscription_id)}]
        ),
        headers=GRAPHQL_HEADERS,
    )

    # then
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["subscriptions"]["page"][0]
    assert customer_data == {
        "customer": {
            "customerId": "59289a57-70fb-4ff5-9c93-10fe67b12434",
            "fullname": "Default::Orchestrator-Core Customer",
            "shortcode": "default-cust",
        }
    }


def test_subscription_customer_overriden(override_class_app_graphql, test_client, sub_one_subscription_1):
    # when
    response = test_client.post(
        GRAPHQL_ENDPOINT,
        content=get_subscriptions_customer_query(
            filter_by=[{"field": "subscriptionId", "value": str(sub_one_subscription_1.subscription_id)}],
            override_fields=True,
        ),
        headers=GRAPHQL_HEADERS,
    )

    # then
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["subscriptions"]["page"][0]

    assert customer_data == {
        "customer": {
            "customerId": "overriden",
            "fullname": "Default::Orchestrator-Core Customer",
            "shortcode": "default-cust",
            "newField": "59289a57-70fb-4ff5-9c93-10fe67b12434",
        }
    }


def test_subscription_detail_customer(fastapi_app_graphql, test_client, sub_one_subscription_1):
    # when
    response = test_client.post(
        GRAPHQL_ENDPOINT,
        content=get_subscriptions_detail_customer_query(
            filter_by=[{"field": "subscriptionId", "value": str(sub_one_subscription_1.subscription_id)}]
        ),
        headers=GRAPHQL_HEADERS,
    )

    # then
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["subscriptions"]["page"][0]
    assert customer_data == {
        "customer": {
            "customerId": "59289a57-70fb-4ff5-9c93-10fe67b12434",
            "fullname": "Default::Orchestrator-Core Customer",
            "shortcode": "default-cust",
        }
    }


def test_subscription_detail_customer_overriden(override_class_app_graphql, test_client, sub_one_subscription_1):
    # when
    response = test_client.post(
        GRAPHQL_ENDPOINT,
        content=get_subscriptions_detail_customer_query(
            filter_by=[{"field": "subscriptionId", "value": str(sub_one_subscription_1.subscription_id)}],
            override_fields=True,
        ),
        headers=GRAPHQL_HEADERS,
    )

    # then
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["subscriptions"]["page"][0]

    assert customer_data == {
        "customer": {
            "customerId": "overriden",
            "fullname": "Default::Orchestrator-Core Customer",
            "shortcode": "default-cust",
            "newField": "59289a57-70fb-4ff5-9c93-10fe67b12434",
        }
    }

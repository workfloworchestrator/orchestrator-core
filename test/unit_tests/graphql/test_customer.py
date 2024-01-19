import json
from http import HTTPStatus

import pytest

from orchestrator.settings import AppSettings
from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


def get_customers_query(
    first: int = 1,
    after: int = 0,
    filter_by: list[str] | None = None,
    sort_by: list[dict[str, str]] | None = None,
) -> bytes:
    query = """
query CustomerQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {
  customers(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {
    page {
      customerId,
      fullname,
      shortcode,
    }
  }
}
    """
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


def test_customers(fastapi_app_graphql, test_client):
    response = test_client.post(GRAPHQL_ENDPOINT, content=get_customers_query(), headers=GRAPHQL_HEADERS)
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]["page"][0]
    assert customer_data == {
        "customerId": "59289a57-70fb-4ff5-9c93-10fe67b12434",
        "fullname": "Default::Orchestrator-Core Customer",
        "shortcode": "default-cust",
    }


def test_change_customer_env_vars(fastapi_app_graphql, test_client):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DEFAULT_CUSTOMER_FULLNAME", "Custom Default Customer")
        mp.setenv("DEFAULT_CUSTOMER_SHORTCODE", "shortcode")
        mp.setenv("DEFAULT_CUSTOMER_IDENTIFIER", "123456")
        new_app_settings = AppSettings()
        mp.setattr("orchestrator.graphql.resolvers.customer.app_settings", new_app_settings)
        response = test_client.post(GRAPHQL_ENDPOINT, content=get_customers_query(), headers=GRAPHQL_HEADERS)

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]["page"][0]
    assert customer_data == {
        "customerId": "123456",
        "fullname": "Custom Default Customer",
        "shortcode": "shortcode",
    }

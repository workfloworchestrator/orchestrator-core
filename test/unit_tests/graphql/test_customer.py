import json
from http import HTTPStatus

import pytest

from orchestrator.settings import AppSettings
from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


def get_customers_query() -> bytes:
    query = """
query CustomerQuery {
  customers {
    fullname,
    shortcode,
    identifier,
  }
}
    """
    return json.dumps({"operationName": "CustomerQuery", "query": query}).encode("utf-8")


def test_customers(test_client):
    response = test_client.post(GRAPHQL_ENDPOINT, content=get_customers_query(), headers=GRAPHQL_HEADERS)
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]
    assert customer_data == {
        "fullname": "Default::Orchestrator-Core Customer",
        "shortcode": "default-cust",
        "identifier": "59289a57-70fb-4ff5-9c93-10fe67b12434",
    }


def test_change_customer_env_vars(test_client):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DEFAULT_CUSTOMER_FULLNAME", "Custom Default Customer")
        mp.setenv("DEFAULT_CUSTOMER_SHORTCODE", "shortcode")
        mp.setenv("DEFAULT_CUSTOMER_IDENTIFIER", "123456")
        new_app_settings = AppSettings()
        mp.setattr("orchestrator.graphql.resolvers.default_customer.app_settings", new_app_settings)
        response = test_client.post(GRAPHQL_ENDPOINT, content=get_customers_query(), headers=GRAPHQL_HEADERS)

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]
    assert customer_data == {
        "fullname": "Custom Default Customer",
        "shortcode": "shortcode",
        "identifier": "123456",
    }

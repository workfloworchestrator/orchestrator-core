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

import json
from http import HTTPStatus

import pytest

from orchestrator.core.settings import AppSettings
from test.integration_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


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


def test_customers(test_client_graphql):
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=get_customers_query(), headers=GRAPHQL_HEADERS)
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]["page"][0]
    assert customer_data == {
        "customerId": "59289a57-70fb-4ff5-9c93-10fe67b12434",
        "fullname": "Default::Orchestrator-Core Customer",
        "shortcode": "default-cust",
    }


def test_change_customer_env_vars(test_client_graphql):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DEFAULT_CUSTOMER_FULLNAME", "Custom Default Customer")
        mp.setenv("DEFAULT_CUSTOMER_SHORTCODE", "shortcode")
        mp.setenv("DEFAULT_CUSTOMER_IDENTIFIER", "123456")
        new_app_settings = AppSettings()
        mp.setattr("orchestrator.core.graphql.resolvers.customer.app_settings", new_app_settings)
        response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=get_customers_query(), headers=GRAPHQL_HEADERS)

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    customer_data = result["data"]["customers"]["page"][0]
    assert customer_data == {
        "customerId": "123456",
        "fullname": "Custom Default Customer",
        "shortcode": "shortcode",
    }

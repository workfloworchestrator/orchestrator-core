# Copyright 2022-2026 SURF.
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
from uuid import uuid4

from test.unit_tests.config import GRAPHQL_ENDPOINT


def build_simple_query(subscription_id):

    q = """query SubscriptionQuery($id: UUID!) {
          subscription(id: $id) {
            insync
            status
            }
        }"""
    return json.dumps(
        {
            "operationName": "SubscriptionQuery",
            "query": q,
            "variables": {
                "id": str(subscription_id),
            },
        }
    ).encode("utf-8")


def build_complex_query(subscription_id):
    q = """query SubscriptionQuery($id: UUID!) {
        subscription(id: $id) {
            insync
            __typename
            product {
                status
            }
            ... on ProductSubListUnionSubscription {
                testBlock {
                    intField
                }
            }
        }
    }"""
    return json.dumps(
        {
            "operationName": "SubscriptionQuery",
            "query": q,
            "variables": {
                "id": str(subscription_id),
            },
        }
    ).encode("utf-8")


def build_last_validation_query(subscription_id):
    q = """query LastValidationQuery($id: UUID!) {
        subscription(id: $id) {
            lastValidatedAt
        }
    }"""
    return json.dumps(
        {
            "operationName": "LastValidationQuery",
            "query": q,
            "variables": {
                "id": str(subscription_id),
            },
        }
    ).encode("utf-8")


def test_last_validation_query(test_client_graphql, validation_workflow_process_instance, benchmark):
    process, process_subscription = validation_workflow_process_instance
    test_query = build_last_validation_query(process_subscription.subscription_id)

    @benchmark
    def response():
        return test_client_graphql.post(
            GRAPHQL_ENDPOINT, content=test_query, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": {"subscription": {"lastValidatedAt": process.last_modified_at.isoformat()}}}


def test_single_simple_subscription(test_client_graphql, product_sub_list_union_subscription_1, benchmark):
    test_query = build_simple_query(subscription_id=product_sub_list_union_subscription_1)

    @benchmark
    def response():
        return test_client_graphql.post(
            GRAPHQL_ENDPOINT, content=test_query, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": {"subscription": {"insync": True, "status": "ACTIVE"}}}


def test_single_complex_subscription(
    test_client_graphql, product_sub_list_union_subscription_1, test_product_type_sub_list_union, benchmark
):
    _, _, ProductSubListUnion = test_product_type_sub_list_union
    test_query = build_complex_query(subscription_id=product_sub_list_union_subscription_1)

    @benchmark
    def response():
        return test_client_graphql.post(
            GRAPHQL_ENDPOINT, content=test_query, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "data": {
            "subscription": {
                "__typename": "ProductSubListUnionSubscription",
                "insync": True,
                "product": {"status": "ACTIVE"},
                "testBlock": {"intField": 1},
            }
        }
    }


def test_subscription_does_not_exist(test_client_graphql, benchmark):
    test_query = build_simple_query(uuid4())

    @benchmark
    def response():
        return test_client_graphql.post(
            GRAPHQL_ENDPOINT, content=test_query, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"data": {"subscription": None}}

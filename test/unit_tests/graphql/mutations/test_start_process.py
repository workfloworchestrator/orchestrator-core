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

from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS
from test.unit_tests.graphql.mutations.helpers import mutation_authorization


def get_start_process_mutation(
    name: str,
    payload: dict,
) -> bytes:
    query = """
mutation StartProcessMutation ($name: String!, $payload: Payload!) {
    startProcess(name: $name, payload: $payload) {
        ... on ProcessCreated {
            id
        }
        ... on MutationError {
            message
            details
        }
    }
}
    """
    return json.dumps(
        {
            "operationName": "StartProcessMutation",
            "query": query,
            "variables": {
                "name": name,
                "payload": payload,
            },
        }
    ).encode("utf-8")


def test_process_not_found(httpx_mock, test_client):
    # given

    unknown_wf = "unknown_wf"

    # when

    query = get_start_process_mutation(name=unknown_wf, payload={"payload": {}})

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    expected = {
        "data": {"startProcess": {"details": "404: Workflow does not exist", "message": "Could not create process"}}
    }

    assert response.status_code == HTTPStatus.OK
    assert response.json() == expected


def test_process_started(httpx_mock, test_client, generic_product_type_1):
    # given

    known_wf = "task_validate_products"

    # when

    query = get_start_process_mutation(name=known_wf, payload={"payload": [{}]})

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data.get("data", {}).get("startProcess", {}).get("id")

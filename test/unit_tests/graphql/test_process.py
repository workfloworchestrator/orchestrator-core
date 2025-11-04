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
from unittest import mock


def build_simple_query(process_id):
    q = """
        query ProcessQuery($processId: UUID!) {
            process(processId: $processId) {
                processId
                userPermissions {
                    retryAllowed
                    resumeAllowed
                }
            }
        }
        """
    return json.dumps(
        {
            "operationName": "ProcessQuery",
            "query": q,
            "variables": {
                "processId": str(process_id),
            },
        }
    ).encode("utf-8")


def test_process(test_client, mocked_processes):
    process_id = mocked_processes[0]
    test_query = build_simple_query(process_id)

    response = test_client.post("/api/graphql", content=test_query, headers={"Content-Type": "application/json"})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "data": {
            "process": {"processId": str(process_id), "userPermissions": {"resumeAllowed": True, "retryAllowed": True}}
        }
    }


@mock.patch("orchestrator.graphql.schemas.process.get_workflow")
def test_process_is_allowed_with_historic_workflow_only_left_in_db(
    mock_get_workflow, test_client, mocked_processes, test_workflow_soft_deleted
):
    mock_get_workflow.return_value = None
    process_id = mocked_processes[0]
    test_query = build_simple_query(process_id)

    response = test_client.post("/api/graphql", content=test_query, headers={"Content-Type": "application/json"})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "data": {
            "process": {"processId": str(process_id), "userPermissions": {"resumeAllowed": True, "retryAllowed": True}}
        }
    }

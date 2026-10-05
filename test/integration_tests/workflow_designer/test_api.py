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

from http import HTTPStatus

import pytest

from orchestrator.core.workflow import ProcessStatus
from orchestrator.core.workflows import get_workflow
from test.integration_tests.config import GRAPHQL_ENDPOINT
from test.integration_tests.workflow_designer.conftest import REPORT, add_process

URL = "/api/workflow-designer"


@pytest.fixture
def report_payload():
    return REPORT.model_dump(mode="json")


def test_steps_describe_core_steps_and_helpers(test_client):
    response = test_client.get(f"{URL}/steps")

    assert response.status_code == HTTPStatus.OK
    steps = {step["id"]: step for step in response.json()}
    store_note = steps["orchestrator.core.workflows.modify_note:store_subscription_note"]
    assert [(i["name"], i["type"]["kind"]) for i in store_note["inputs"]] == [
        ("subscription_id", "uuid"),
        ("note", "str"),
    ]
    assert steps["designer:log_message"]["kind"] == "helper"


def test_crud(test_client, report_payload):
    created = test_client.post(f"{URL}/workflows", json=report_payload)
    assert created.status_code == HTTPStatus.CREATED
    assert get_workflow(REPORT.name) is not None

    listed = test_client.get(f"{URL}/workflows").json()
    assert [(w["definition"]["name"], w["version"]) for w in listed] == [(REPORT.name, 1)]

    updated = test_client.put(f"{URL}/workflows/{REPORT.name}", json=report_payload)
    assert updated.json()["version"] == 2

    add_process(REPORT.name, ProcessStatus.COMPLETED)
    assert test_client.get(f"{URL}/workflows/{REPORT.name}").json()["process_count"] == 1
    assert test_client.delete(f"{URL}/workflows/{REPORT.name}").json() == {"result": "archived"}
    assert test_client.get(f"{URL}/workflows/{REPORT.name}").status_code == HTTPStatus.NOT_FOUND


def test_create_invalid_chain_returns_issues(test_client, report_payload):
    response = test_client.post(f"{URL}/workflows", json=report_payload | {"form_fields": []})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    issues = response.json()["detail"]["validation"]["issues"]
    assert {(issue["position"], issue["input"]) for issue in issues} >= {(0, "subscription_id"), (0, "note")}


def test_designed_task_in_graphql(test_client_graphql, report_payload):
    test_client_graphql.post(f"{URL}/workflows", json=report_payload)
    query = '{ workflows(filterBy: [{field: "name", value: "designed_note_report"}]) { page { name isTask isAllowed steps { name } } } }'

    response = test_client_graphql.post(GRAPHQL_ENDPOINT, json={"query": query})

    assert "errors" not in response.json()
    assert response.json()["data"]["workflows"]["page"] == [
        {
            "name": REPORT.name,
            "isTask": True,
            "isAllowed": True,
            "steps": [{"name": n} for n in ["Start", "Store note", "Set checked_by", "Log message", "Done"]],
        }
    ]

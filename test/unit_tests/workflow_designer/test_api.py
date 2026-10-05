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

"""The REST contract the UI depends on; the service behind it is tested against a database in integration tests."""

from http import HTTPStatus
from unittest import mock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from orchestrator.core.api.api_v1.endpoints.processes import user_name
from orchestrator.core.app import OrchestratorCore
from orchestrator.core.settings import app_settings
from orchestrator.core.workflow_designer import api
from orchestrator.core.workflow_designer.definition import WorkflowDefinition
from orchestrator.core.workflow_designer.service import DesignerError, StoredWorkflow
from test.unit_tests.api.test_endpoint_guardrails import _iter_api_routes

DEFINITION = {
    "name": "designed_note",
    "description": "Set a value",
    "form_fields": [],
    "steps": [{"step_id": "designer:set_value", "config": {"key": "checked_by", "value": "x"}}],
}
STORED = StoredWorkflow(
    definition=WorkflowDefinition.model_validate(DEFINITION), version=2, created_by="jane", process_count=1
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "all_steps", lambda rescan=False: {})
    app = FastAPI()
    app.include_router(api.router, prefix="/api/workflow-designer")
    app.dependency_overrides[user_name] = lambda: "jane"
    return TestClient(app)


def test_info(client):
    response = client.get("/api/workflow-designer/info")

    assert response.json() == {"name_prefix": app_settings.WORKFLOW_DESIGNER_NAME_PREFIX, "step_count": 0}


def test_field_types(client):
    keys = [field_type["key"] for field_type in client.get("/api/workflow-designer/field-types").json()]

    assert keys == ["string", "text", "integer", "boolean", "uuid", "choice", "customer"]


def test_validate_reports_issues_and_palette(client):
    response = client.post(
        "/api/workflow-designer/validate",
        json={"definition": DEFINITION | {"steps": [{"step_id": "app:gone"}]}, "insert_at": 0},
    )

    body = response.json()
    assert response.status_code == HTTPStatus.OK
    assert body["valid"] is False
    assert body["issues"][0]["step_id"] == "app:gone"
    assert body["palette"]["designer:set_value"]["status"] == "ok"


@pytest.mark.parametrize(
    ("method", "path", "service_call", "payload", "status"),
    [
        pytest.param("get", "/workflows/designed_note", "get_workflow_definition", None, HTTPStatus.OK, id="get"),
        pytest.param("post", "/workflows", "create_workflow", DEFINITION, HTTPStatus.CREATED, id="create"),
        pytest.param("put", "/workflows/designed_note", "update_workflow", DEFINITION, HTTPStatus.OK, id="update"),
    ],
)
def test_stored_workflow_responses(client, method, path, service_call, payload, status):
    with mock.patch.object(api, service_call, return_value=STORED):
        response = getattr(client, method)(f"/api/workflow-designer{path}", **({"json": payload} if payload else {}))

    assert response.status_code == status
    assert response.json() == {"definition": DEFINITION, "version": 2, "created_by": "jane", "process_count": 1}


def test_list_and_delete(client):
    with mock.patch.object(api, "list_workflows", return_value=[STORED]):
        assert [w["definition"]["name"] for w in client.get("/api/workflow-designer/workflows").json()] == [
            "designed_note"
        ]
    with mock.patch.object(api, "delete_workflow", return_value="archived"):
        assert client.delete("/api/workflow-designer/workflows/designed_note").json() == {"result": "archived"}


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(DesignerError("gone", "not_found"), HTTPStatus.NOT_FOUND, id="not-found"),
        pytest.param(DesignerError("taken", "conflict"), HTTPStatus.CONFLICT, id="conflict"),
        pytest.param(DesignerError("bad", "invalid", {"valid": False}), HTTPStatus.BAD_REQUEST, id="invalid"),
    ],
)
def test_service_errors_map_to_statuses(client, error, status):
    with mock.patch.object(api, "update_workflow", side_effect=error):
        response = client.put("/api/workflow-designer/workflows/designed_note", json=DEFINITION)

    assert response.status_code == status
    assert response.json()["detail"] == {"message": str(error), "validation": error.detail}


def test_request_validation_rejects_names_without_prefix(client):
    response = client.post("/api/workflow-designer/workflows", json=DEFINITION | {"name": "task_x"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    ("enabled", "mounted"), [pytest.param(True, True, id="enabled"), pytest.param(False, False, id="disabled")]
)
def test_router_is_only_mounted_when_enabled(enabled, mounted):
    with (
        mock.patch("orchestrator.core.app.init_database"),
        mock.patch.object(app_settings, "WORKFLOW_DESIGNER_ENABLED", enabled),
    ):
        app = OrchestratorCore()

    endpoints = {route.endpoint for route in _iter_api_routes(app.router)}
    assert (api.get_workflows in endpoints) is mounted

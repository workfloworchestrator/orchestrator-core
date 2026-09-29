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

from orchestrator.core.settings import app_settings


@pytest.fixture()
def guide_dir(tmp_path, monkeypatch):
    """Temporary directory configured as WORKFLOW_USER_GUIDE_DIR."""
    monkeypatch.setattr(app_settings, "WORKFLOW_USER_GUIDE_DIR", tmp_path)
    return tmp_path


def test_get_workflow_guide_not_found(test_client, guide_dir):
    response = test_client.get("/api/workflow_user_guides/some_workflow")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_workflow_guide_found(test_client, guide_dir):
    (guide_dir / "some_workflow.md").write_text("# Some Workflow", encoding="utf-8")
    response = test_client.get("/api/workflow_user_guides/some_workflow")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == "# Some Workflow"


def test_get_workflow_guide_invalid_name_pattern(test_client):
    response = test_client.get("/api/workflow_user_guides/Invalid-Name")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

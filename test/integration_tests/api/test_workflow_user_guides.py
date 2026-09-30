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
from pathlib import Path

import pytest

from orchestrator.core.settings import app_settings


@pytest.fixture()
def guide_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temporary directory configured as WORKFLOW_USER_GUIDE_DIR."""
    monkeypatch.setattr(app_settings, "WORKFLOW_USER_GUIDE_DIR", tmp_path)
    return tmp_path


def test_get_workflow_guide_not_found(test_client, guide_dir: Path) -> None:
    response = test_client.get("/api/workflow_user_guides/some_workflow")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_workflow_guide_found(test_client, guide_dir: Path) -> None:
    (guide_dir / "some_workflow.md").write_text("# Some Workflow", encoding="utf-8")
    response = test_client.get("/api/workflow_user_guides/some_workflow")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == "# Some Workflow"


@pytest.mark.parametrize(
    "workflow_name",
    [
        pytest.param("Invalid-Name", id="uppercase-and-hyphen"),
        pytest.param("1_workflow", id="leading-digit"),
        pytest.param("some_workflow.md", id="extension"),
        pytest.param("%2e%2e", id="url-encoded-parent-directory"),
        pytest.param("some_workflow%00", id="null-byte"),
        pytest.param("some_workflow;id", id="semicolon"),
    ],
)
def test_get_workflow_guide_invalid_name(test_client, guide_dir: Path, workflow_name: str) -> None:
    (guide_dir.parent / "secret.md").write_text("secret", encoding="utf-8")
    response = test_client.get(f"/api/workflow_user_guides/{workflow_name}")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/workflow_user_guides/../secret", id="parent-traversal"),
        pytest.param("/api/workflow_user_guides/..", id="parent-directory"),
        pytest.param("/api/workflow_user_guides/..%2fsecret", id="url-encoded-traversal"),
        pytest.param("/api/workflow_user_guides/nested/some_workflow", id="subdirectory"),
    ],
)
def test_get_workflow_guide_path_traversal_does_not_leak(test_client, guide_dir: Path, path: str) -> None:
    (guide_dir.parent / "secret.md").write_text("secret", encoding="utf-8")
    response = test_client.get(path)
    assert response.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY)
    assert "secret" not in response.text

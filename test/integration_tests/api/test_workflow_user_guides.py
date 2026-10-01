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
from fastapi.testclient import TestClient

from orchestrator.core.settings import app_settings


@pytest.fixture()
def guide_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temporary directory configured as WORKFLOW_USER_GUIDE_DIR."""
    monkeypatch.setattr(app_settings, "WORKFLOW_USER_GUIDE_DIR", tmp_path)
    return tmp_path


def test_get_workflow_guide_not_found(test_client: TestClient, guide_dir: Path) -> None:
    response = test_client.get("/api/workflow_user_guides/some_workflow")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Workflow guide not found"}


@pytest.mark.parametrize("content", ["# Some Workflow", "", "<script>alert('test')</script>"])
def test_get_workflow_guide_found(test_client: TestClient, guide_dir: Path, content: str) -> None:
    (guide_dir / "some_workflow.md").write_text(content, encoding="utf-8")
    response = test_client.get("/api/workflow_user_guides/some_workflow")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == content


@pytest.mark.parametrize(
    "workflow_name",
    [
        pytest.param("some_workflow%00", id="null-byte"),
        pytest.param("some_workflow;id", id="semicolon"),
        pytest.param("some%20workflow", id="space"),
    ],
)
def test_get_workflow_guide_invalid_name(test_client: TestClient, guide_dir: Path, workflow_name: str) -> None:
    (guide_dir.parent / "secret.md").write_text("secret", encoding="utf-8")
    response = test_client.get(f"/api/workflow_user_guides/{workflow_name}")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/workflow_user_guides/../secret", id="parent-traversal"),
        pytest.param("/api/workflow_user_guides/..", id="parent-directory"),
        pytest.param("/api/workflow_user_guides/..%2fsecret", id="url-encoded-traversal"),
        pytest.param("/api/workflow_user_guides/%2e%2e", id="url-encoded-parent-directory"),
        pytest.param("/api/workflow_user_guides/nested/some_workflow", id="subdirectory"),
    ],
)
def test_get_workflow_guide_path_traversal_does_not_leak(test_client: TestClient, guide_dir: Path, path: str) -> None:
    (guide_dir.parent / "secret.md").write_text("secret", encoding="utf-8")
    response = test_client.get(path)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "secret" not in response.text


@pytest.mark.parametrize("target_exists", [True, False], ids=["existing-target", "missing-target"])
def test_get_workflow_guide_symlink_outside_directory_returns_not_found(
    test_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_exists: bool
) -> None:
    guide_dir = tmp_path / "guides"
    guide_dir.mkdir()
    target = tmp_path / "secret.md"
    if target_exists:
        target.write_text("Confidential guide content", encoding="utf-8")
    (guide_dir / "some_workflow.md").symlink_to(target)
    monkeypatch.setattr(app_settings, "WORKFLOW_USER_GUIDE_DIR", guide_dir)

    response = test_client.get("/api/workflow_user_guides/some_workflow")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Workflow guide not found"}

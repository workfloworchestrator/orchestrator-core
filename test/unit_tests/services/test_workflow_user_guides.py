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

import pytest

from orchestrator.core.services.workflow_user_guides import get_workflow_guide
from orchestrator.core.settings import app_settings


@pytest.fixture()
def guide_dir(tmp_path, monkeypatch):
    """Temporary directory configured as WORKFLOW_USER_GUIDE_DIR."""
    monkeypatch.setattr(app_settings, "WORKFLOW_USER_GUIDE_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def no_guide_dir(monkeypatch):
    """Ensure WORKFLOW_USER_GUIDE_DIR is None for the duration of the test."""
    monkeypatch.setattr(app_settings, "WORKFLOW_USER_GUIDE_DIR", None)


async def test_returns_none_when_guide_dir_not_configured(no_guide_dir):
    assert await get_workflow_guide("some_workflow") is None


async def test_returns_none_when_guide_file_missing(guide_dir):
    assert await get_workflow_guide("nonexistent_workflow") is None


@pytest.mark.parametrize(
    ("workflow_name", "content"),
    [
        pytest.param("create_network", "# Create Network\n\nStep 1: ...", id="simple-guide"),
        pytest.param("empty_workflow", "", id="empty-file"),
    ],
)
async def test_returns_guide_content_when_file_exists(guide_dir, workflow_name, content):
    (guide_dir / f"{workflow_name}.md").write_text(content, encoding="utf-8")
    assert await get_workflow_guide(workflow_name) == content


async def test_does_not_return_guide_for_different_workflow(guide_dir):
    (guide_dir / "workflow_a.md").write_text("Guide A", encoding="utf-8")
    assert await get_workflow_guide("workflow_b") is None


async def test_guide_content_is_read_as_utf8(guide_dir):
    content = "# Gids\n\nStap één: configureer het netwerk."
    (guide_dir / "dutch_workflow.md").write_text(content, encoding="utf-8")
    assert await get_workflow_guide("dutch_workflow") == content

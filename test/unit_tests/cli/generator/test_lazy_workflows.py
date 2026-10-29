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

"""Tests for registering LazyWorkflowInstance entries in ``workflows/__init__.py``."""

from pathlib import Path

import pytest

from orchestrator.core.cli.generate import get_template_environment
from orchestrator.core.cli.generator.generator.settings import product_generator_settings
from orchestrator.core.cli.generator.generator.workflow import insert_lazy_workflow_instances

IMPORT_LINE = "from orchestrator.core.workflows import LazyWorkflowInstance\n"


@pytest.fixture
def folder_prefix(tmp_path, monkeypatch):
    # The generator works with paths relative to the current directory, like the CLI does
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(product_generator_settings, "FOLDER_PREFIX", Path(""))
    return tmp_path


def write_to_disk(path: Path, content: str, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a" if append else "w") as fp:
        fp.write(content)


def workflows_init(folder_prefix: Path) -> Path:
    return folder_prefix / "workflows" / "__init__.py"


def test_creates_init_with_import(folder_prefix) -> None:
    insert_lazy_workflow_instances(get_template_environment(), {"variable": "example"}, write_to_disk)

    content = workflows_init(folder_prefix).read_text()
    assert content.startswith(IMPORT_LINE)
    assert 'LazyWorkflowInstance("workflows.example.create_example", "create_example")' in content


def test_appends_to_existing_init_with_import(folder_prefix) -> None:
    insert_lazy_workflow_instances(get_template_environment(), {"variable": "example"}, write_to_disk)
    insert_lazy_workflow_instances(get_template_environment(), {"variable": "other"}, write_to_disk)

    content = workflows_init(folder_prefix).read_text()
    assert content.count(IMPORT_LINE.strip()) == 1
    assert 'LazyWorkflowInstance("workflows.example.create_example", "create_example")' in content
    assert 'LazyWorkflowInstance("workflows.other.create_other", "create_other")' in content


def test_adds_missing_import_to_precreated_init(folder_prefix) -> None:
    """``create_dunder_init_files`` pre-creates an empty ``workflows/__init__.py`` (#1864)."""
    init = workflows_init(folder_prefix)
    init.parent.mkdir(parents=True)
    init.touch()

    insert_lazy_workflow_instances(get_template_environment(), {"variable": "example"}, write_to_disk)

    content = init.read_text()
    assert IMPORT_LINE.strip() in content
    assert 'LazyWorkflowInstance("workflows.example.create_example", "create_example")' in content


def test_does_not_re_add_existing_product(folder_prefix) -> None:
    insert_lazy_workflow_instances(get_template_environment(), {"variable": "example"}, write_to_disk)
    before = workflows_init(folder_prefix).read_text()

    insert_lazy_workflow_instances(get_template_environment(), {"variable": "example"}, write_to_disk)

    assert workflows_init(folder_prefix).read_text() == before

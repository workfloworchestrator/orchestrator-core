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

"""Tests for generating the shared subscription description service."""

from pathlib import Path
from unittest import mock

import pytest

from orchestrator.core.cli.generate import get_template_environment
from orchestrator.core.cli.generator.generator.helpers import (
    get_description_service_module,
    get_description_service_path,
)
from orchestrator.core.cli.generator.generator.settings import product_generator_settings
from orchestrator.core.cli.generator.generator.workflow import generate_description_service


@pytest.fixture
def folder_prefix(tmp_path, monkeypatch):
    # The generator works with paths relative to the current directory, like the CLI does
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(product_generator_settings, "FOLDER_PREFIX", Path(""))
    return tmp_path


def write_to_disk(path: Path, content: str, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_description_service_location(folder_prefix) -> None:
    assert get_description_service_path() == Path("products/services/description.py")
    assert get_description_service_module() == "products.services.description"


def test_creates_description_service_when_missing(folder_prefix) -> None:
    config = {"type": "CoreLink", "variable": "core_link"}
    writer = mock.MagicMock(side_effect=write_to_disk)

    generate_description_service(get_template_environment(), config, writer)

    writer.assert_called_once()
    path, content = writer.call_args.args
    assert path == Path("products/services/description.py")
    assert "@singledispatch\ndef description(" in content
    assert "return single_dispatch_base(description, model)" in content
    assert f"import {config['type']}Provisioning\n" in content
    assert f"def _({config['variable']}: {config['type']}Provisioning) -> str:" in content
    assert f'return f"{{{config["variable"]}.product.name}} subscription"' in content
    assert (folder_prefix / "products/services/__init__.py").exists()


def test_appends_to_existing_description_service(folder_prefix) -> None:
    environment = get_template_environment()
    generate_description_service(environment, {"type": "Node", "variable": "node"}, write_to_disk)
    generate_description_service(environment, {"type": "Port", "variable": "port"}, write_to_disk)

    content = (folder_prefix / "products/services/description.py").read_text()
    assert content.count("@singledispatch") == 1
    assert content.count("@description.register") == 2
    assert content.index("import NodeProvisioning") < content.index("@singledispatch")
    assert content.index("import PortProvisioning") < content.index("@singledispatch")
    assert content.index("def _(node: NodeProvisioning)") < content.index("def _(port: PortProvisioning)")


def test_does_not_re_add_existing_product(folder_prefix) -> None:
    environment = get_template_environment()
    config = {"type": "Node", "variable": "node"}
    generate_description_service(environment, config, write_to_disk)
    writer = mock.MagicMock()

    generate_description_service(environment, config, writer)

    writer.assert_not_called()


@pytest.mark.parametrize(
    "import_line",
    [
        pytest.param("from products.product_types.node import Node, NodeProvisioning\n", id="grouped-import"),
        pytest.param(
            "from products.product_types.node import (\n    Node,\n    NodeProvisioning,\n)\n", id="multiline-import"
        ),
    ],
)
def test_preserves_custom_description_when_import_is_reformatted(folder_prefix, import_line: str) -> None:
    environment = get_template_environment()
    config = {"type": "Node", "variable": "node"}
    generate_description_service(environment, config, write_to_disk)
    path = folder_prefix / "products/services/description.py"
    customised = (
        path.read_text()
        .replace("from products.product_types.node import NodeProvisioning\n", import_line)
        .replace('return f"{node.product.name} subscription"', 'return f"Custom {node.node.node_name}"')
    )
    path.write_text(customised)
    writer = mock.MagicMock()

    generate_description_service(environment, config, writer)

    writer.assert_not_called()
    assert path.read_text() == customised


def test_does_not_match_product_with_same_prefix(folder_prefix) -> None:
    environment = get_template_environment()
    generate_description_service(environment, {"type": "NodePort", "variable": "node_port"}, write_to_disk)
    writer = mock.MagicMock(side_effect=write_to_disk)

    generate_description_service(environment, {"type": "Node", "variable": "node"}, writer)

    writer.assert_called_once()
    content = (folder_prefix / "products/services/description.py").read_text()
    assert content.count("@description.register") == 2


def test_dryrun_does_not_create_dunder_init(folder_prefix) -> None:
    services = folder_prefix / "products/services"
    services.mkdir(parents=True)
    writer = mock.MagicMock()

    generate_description_service(get_template_environment(), {"type": "Node", "variable": "node"}, writer, dryrun=True)

    writer.assert_called_once()
    assert not (services / "__init__.py").exists()
    assert not (services / "description.py").exists()

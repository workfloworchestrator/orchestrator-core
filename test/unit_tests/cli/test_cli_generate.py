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

import pathlib
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from orchestrator.core.cli.generate import app
from orchestrator.core.domain.base import ProductBlockModel
from orchestrator.core.types import SubscriptionLifecycle


class MyExistingProductBlockInactive(ProductBlockModel, product_block_name="My Existing Product Block"):
    user_id: int | None = None


class MyExistingProductBlockProvisioning(
    MyExistingProductBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    user_id: int


class MyExistingProductBlock(MyExistingProductBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    pass


def read_file(path: str) -> str:
    file = Path(__file__).resolve().parent / "data" / path
    return str(file)


def test_generate_product():
    runner = CliRunner()
    result = runner.invoke(app, ["product", "--config-file", read_file("product_config3.yaml"), "--dryrun"])
    assert "class MyProductInactive" in result.stdout
    assert "class MyProductProvisioning" in result.stdout
    assert "class MyProduct" in result.stdout
    assert result.exit_code == 0


@mock.patch("orchestrator.core.cli.generator.generator.product_block.get_existing_product_blocks")
def test_generate_product_blocks(existing_product_blocks_mock):
    existing_product_blocks_mock.return_value = {
        "MyExistingProductBlock": "products.product_blocks.my_existing_product_block"
    }
    runner = CliRunner()
    result = runner.invoke(app, ["product-blocks", "--config-file", read_file("product_config3.yaml"), "--dryrun"])
    assert "class MyIntermediateProductBlockInactive" in result.stdout
    assert "class MyIntermediateProductBlockProvisioning" in result.stdout
    assert "class MyIntermediateProductBlock" in result.stdout
    assert result.exit_code == 0


def test_generate_workflows():
    runner = CliRunner()
    result = runner.invoke(app, ["workflows", "--config-file", read_file("product_config3.yaml"), "--dryrun"])
    assert "@create_workflow(" in result.stdout
    assert "@modify_workflow(" in result.stdout
    assert "@terminate_workflow(" in result.stdout
    assert "@validate_workflow(" in result.stdout
    assert result.exit_code == 0


@mock.patch.object(pathlib.Path, "mkdir")
def test_generate_unit_tests(mkdir_mock):
    runner = CliRunner()
    result = runner.invoke(app, ["unit-tests", "--config-file", read_file("product_config3.yaml"), "--dryrun"])
    assert "def test_" in result.stdout
    assert result.exit_code == 0

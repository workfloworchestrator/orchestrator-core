# Copyright 2019-2020 SURF.
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

from collections.abc import Callable
from pathlib import Path

import structlog
from jinja2 import Environment

from orchestrator.cli.generator.generator.helpers import (
    get_all_fields,
    get_product_file_name,
    get_product_types_module,
    get_workflow,
    root_product_block,
)
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings
from orchestrator.cli.generator.generator.validations import get_validations

logger = structlog.getLogger(__name__)


def get_test_product_path(config: dict) -> Path:
    file_name = f"test_{get_product_file_name(config)}"
    return settings.TEST_PRODUCT_TYPE_PATH / Path(file_name).with_suffix(".py")


def generate_product_type_tests(environment: Environment, config: dict, writer: Callable) -> None:
    template = environment.get_template("test_product_type.j2")
    content = template.render(product=config, product_types_module=get_product_types_module())

    path = get_test_product_path(config)
    writer(path, content)


def get_test_workflow_path(config: dict, workflow_type: str) -> Path:
    file_name = get_product_file_name(config)
    folder = file_name

    workflow_folder = settings.TEST_WORKFLOWS_PATH / Path(folder)
    Path(workflow_folder).mkdir(parents=True, exist_ok=True)

    return workflow_folder / Path(f"test_{workflow_type}_{file_name}").with_suffix(".py")


def generate_workflow_tests(environment: Environment, config: dict, writer: Callable) -> None:
    generate_test_create_workflow(environment, config, writer)
    generate_test_modify_workflow(environment, config, writer)
    generate_test_validate_workflow(environment, config, writer)
    generate_test_terminate_workflow(environment, config, writer)


def generate_test_create_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    product_block = root_product_block(config)
    fields = get_all_fields(product_block)
    validations, _ = get_validations(fields)

    template = environment.get_template("test_create_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=get_product_types_module())

    path = get_test_workflow_path(config, "create")
    writer(path, content)


def generate_test_modify_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    product_block = root_product_block(config)
    fields = get_all_fields(product_block)
    validations, _ = get_validations(fields)

    template = environment.get_template("test_modify_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=get_product_types_module())

    path = get_test_workflow_path(config, "modify")
    writer(path, content)


def generate_test_validate_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    workflow = get_workflow(config, "validate")
    validations = workflow.get("validations", [])

    template = environment.get_template("test_validate_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=get_product_types_module())

    path = get_test_workflow_path(config, "validate")
    writer(path, content)


def generate_test_terminate_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    workflow = get_workflow(config, "terminate")
    validations = workflow.get("validations", [])

    template = environment.get_template("test_terminate_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=get_product_types_module())

    path = get_test_workflow_path(config, "terminate")
    writer(path, content)


def generate_unit_tests(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    generate_product_type_tests(environment, config, writer)
    generate_workflow_tests(environment, config, writer)

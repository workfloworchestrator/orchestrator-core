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
from typing import Any

import structlog
from jinja2 import Environment

from orchestrator.cli.generator.generator.helpers import get_product_file_name, get_workflow, product_types_module
from orchestrator.cli.generator.generator.settings import product_generator_settings
from orchestrator.cli.generator.generator.validations import get_validations

logger = structlog.getLogger(__name__)


def get_test_product_path(config: dict) -> str:
    file_name = f"test_{get_product_file_name(config)}"
    return f"{product_generator_settings.TEST_PRODUCT_TYPE_PATH}/{file_name}.py"


def generate_product_type_tests(environment: Environment, config: dict, writer: Callable, **_kwargs: Any) -> None:
    template = environment.get_template("test_product_type.j2")
    content = template.render(product=config, product_types_module=product_types_module)

    path = get_test_product_path(config)
    writer(path, content)


def get_test_workflow_folder(config: dict) -> str:
    file_name = get_product_file_name(config)
    folder = file_name

    return f"{product_generator_settings.TEST_WORKFLOWS_PATH}/{folder}"


def create_test_workflow_folder(config: dict, mkdir: Callable) -> None:
    workflow_folder = get_test_workflow_folder(config)
    mkdir(workflow_folder)


def get_test_workflow_path(workflow_type: str, config: dict) -> str:
    workflow_folder = get_test_workflow_folder(config)
    file_name = get_product_file_name(config)

    return f"{workflow_folder}/test_{workflow_type}_{file_name}.py"


def generate_workflow_tests(context: dict) -> None:
    create_test_workflow_folder(context["config"], context["mkdir"])

    generate_test_create_workflow(**context)
    generate_test_modify_workflow(**context)
    generate_test_validate_workflow(**context)
    generate_test_terminate_workflow(**context)


def generate_test_create_workflow(environment: Environment, config: dict, writer: Callable, **_kwargs: Any) -> None:
    validations, _ = get_validations(config)

    template = environment.get_template("test_create_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=product_types_module)

    path = get_test_workflow_path("create", config)
    writer(path, content)


def generate_test_modify_workflow(environment: Environment, config: dict, writer: Callable, **_kwargs: Any) -> None:
    validations, _ = get_validations(config)

    template = environment.get_template("test_modify_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=product_types_module)

    path = get_test_workflow_path("modify", config)
    writer(path, content)


def generate_test_validate_workflow(environment: Environment, config: dict, writer: Callable, **_kwargs: Any) -> None:
    workflow = get_workflow(config, "validate")
    validations = workflow.get("validations", [])

    template = environment.get_template("test_validate_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=product_types_module)

    path = get_test_workflow_path("validate", config)
    writer(path, content)


def generate_test_terminate_workflow(environment: Environment, config: dict, writer: Callable, **_kwargs: Any) -> None:
    workflow = get_workflow(config, "terminate")
    validations = workflow.get("validations", [])

    template = environment.get_template("test_terminate_workflow.j2")
    content = template.render(product=config, validations=validations, product_types_module=product_types_module)

    path = get_test_workflow_path("terminate", config)
    writer(path, content)


def generate_unit_tests(context: dict) -> None:
    generate_product_type_tests(**context)
    generate_workflow_tests(context)

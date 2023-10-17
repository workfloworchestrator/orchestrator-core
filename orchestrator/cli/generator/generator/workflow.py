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
from functools import partial, wraps
from pathlib import Path
from typing import Any, Optional

import structlog
from jinja2 import Environment

from orchestrator.cli.generator.generator.helpers import (
    get_product_file_name,
    get_workflow,
    product_types_module,
    root_product_block,
)
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings
from orchestrator.cli.generator.generator.translations import add_workflow_translations
from orchestrator.cli.generator.generator.validations import get_validations, get_validations_for_modify

logger = structlog.getLogger(__name__)


def find_field_with_name(config: dict, field_name: str) -> dict:
    product_blocks = config.get("product_blocks", [])
    for pb in product_blocks:
        for field in pb.get("fields", []):
            if field["name"] == field_name:
                return {f"{field_name}_path": pb["name"]}
    return {}


def add_optional_ims_config(config: dict) -> dict:
    if found := find_field_with_name(config, "ims_circuit_id"):
        return config | found
    return config


def add_optional_nso_config(config: dict) -> dict:
    if found := find_field_with_name(config, "nso_service_id"):
        return config | found
    return config


def insert_lazy_workflow_instances(environment: Environment, config: dict, writer: Callable) -> None:
    template = environment.get_template("lazy_workflow_instance.j2")
    variable = config.get("variable", "")
    # product_blocks = config.get("product_blocks", [])
    content = template.render(product=config)

    path = settings.FOLDER_PREFIX / settings.WORKFLOWS_PATH / Path("__init__.py")
    if not path.exists():
        writer(path, "from orchestrator.workflows import LazyWorkflowInstance\n\n")
    with open(path, "r") as fp:
        if f"workflows.{variable}.create_{variable}" in fp.read():
            logger.warning("not re-adding lazy workflows", product=variable)
        else:
            fp.close()
            writer(path, content, append=True)


def generate_workflows(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    create_workflow_paths(config)

    config = add_optional_nso_config(config)
    config = add_optional_ims_config(config)

    generate_shared_workflow_files(environment, config, writer)
    generate_create_workflow(environment, config, writer)
    generate_modify_workflow(environment, config, writer)
    generate_validate_workflow(environment, config, writer)
    generate_terminate_workflow(environment, config, writer)

    add_workflow_translations(config, writer)

    insert_lazy_workflow_instances(environment, config, writer)


def workflow_folder(config: dict) -> Path:
    folder = get_product_file_name(config)
    return settings.FOLDER_PREFIX / settings.WORKFLOWS_PATH / Path(folder)


def shared_workflow_folder(config: dict) -> Path:
    return workflow_folder(config) / Path("shared")


def create_workflow_paths(config: dict) -> None:
    path = workflow_folder(config) / Path("shared")
    path.mkdir(parents=True, exist_ok=True)


def get_workflow_path(config: dict, workflow_type: str) -> Path:
    file_name = get_product_file_name(config)
    return workflow_folder(config) / Path(f"{workflow_type}_{file_name}").with_suffix(".py")


def generate_shared_workflow_files(environment: Environment, config: dict, writer: Callable) -> None:
    product_block = root_product_block(config)
    validations, _ = get_validations(config)

    template = environment.get_template("shared_forms.j2")
    content = template.render(product=config, product_block=product_block, validations=validations)

    path = shared_workflow_folder(config) / Path("forms.py")

    writer(path, content)


def generate_workflow(f: Optional[Callable] = None, workflow: Optional[str] = None) -> Callable:
    if f is None:
        return partial(generate_workflow, workflow=workflow)

    @wraps(f)
    def wrapper(environment: Environment, config: dict, writer: Callable) -> Any:
        def workflow_enabled() -> bool:
            return all(wf.get("enabled", True) for wf in config.get("workflows", []) if wf["name"] == workflow)

        if workflow_enabled():
            return f(environment, config, writer)
        return None

    return wrapper


@generate_workflow(workflow="create")
def generate_create_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    product_block = root_product_block(config)
    validations, validation_imports = get_validations(config)

    template = environment.get_template("create_product.j2")
    content = template.render(
        product=config,
        product_block=product_block,
        validations=validations,
        validation_imports=validation_imports,
        product_types_module=product_types_module,
    )

    path = get_workflow_path(config, "create")

    writer(path, content)


@generate_workflow(workflow="modify")
def generate_modify_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    product_block = root_product_block(config)
    validations, validation_imports = get_validations_for_modify(config)

    template = environment.get_template("modify_product.j2")
    content = template.render(
        product=config,
        product_block=product_block,
        validations=validations,
        validation_imports=validation_imports,
        product_types_module=product_types_module,
    )

    path = get_workflow_path(config, "modify")

    writer(path, content)


@generate_workflow(workflow="validate")
def generate_validate_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    workflow = get_workflow(config, "validate")
    validations = workflow.get("validations", [])

    template = environment.get_template("validate_product.j2")
    content = template.render(product=config, validations=validations, product_types_module=product_types_module)

    path = get_workflow_path(config, "validate")

    writer(path, content)


@generate_workflow(workflow="terminate")
def generate_terminate_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    workflow = get_workflow(config, "terminate")
    validations = workflow.get("validations", [])

    template = environment.get_template("terminate_product.j2")
    content = template.render(product=config, validations=validations, product_types_module=product_types_module)

    path = get_workflow_path(config, "terminate")

    writer(path, content)

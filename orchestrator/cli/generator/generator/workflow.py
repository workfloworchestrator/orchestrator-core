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
from importlib import metadata
from pathlib import Path
from typing import Any

import semver
import structlog
from jinja2 import Environment

from orchestrator.cli.generator.generator.enums import get_int_enums, get_str_enums
from orchestrator.cli.generator.generator.helpers import (
    get_constrained_ints,
    get_existing_product_blocks,
    get_input_fields,
    get_name_spaced_types_to_import,
    get_product_blocks_module,
    get_product_file_name,
    get_product_types_module,
    get_workflow,
    get_workflows_folder,
    get_workflows_module,
    merge_fields,
    root_product_block,
)
from orchestrator.cli.generator.generator.translations import add_workflow_translations
from orchestrator.cli.generator.generator.validations import get_validations

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
    content = template.render(
        product=config,
    )

    path = get_workflows_folder() / Path("__init__.py")
    if path.exists():
        with open(path) as fp:
            if f"workflows.{variable}.create_{variable}" in fp.read():
                logger.warning("not re-adding lazy workflows", product=variable)
            else:
                fp.close()
                writer(path, content, append=True)
    else:
        import_statement = "from orchestrator.workflows import LazyWorkflowInstance\n\n"
        writer(path, import_statement + content)  # will create file if not dryrun


def generate_workflows(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    create_product_workflow_paths(config)

    # TODO: Remove from core and extend config from client specific code
    config = add_optional_nso_config(config)
    config = add_optional_ims_config(config)

    generate_shared_workflow_files(environment, config, writer)
    generate_create_workflow(environment, config, writer)
    generate_modify_workflow(environment, config, writer)
    generate_validate_workflow(environment, config, writer)
    generate_terminate_workflow(environment, config, writer)

    add_workflow_translations(config, writer)

    insert_lazy_workflow_instances(environment, config, writer)


def product_workflow_folder(config: dict) -> Path:
    folder = get_product_file_name(config)
    return get_workflows_folder() / Path(folder)


def shared_product_workflow_folder(config: dict) -> Path:
    return product_workflow_folder(config) / Path("shared")


def create_product_workflow_paths(config: dict) -> None:
    path = product_workflow_folder(config) / Path("shared")
    path.mkdir(parents=True, exist_ok=True)


def get_product_workflow_path(config: dict, workflow_type: str) -> Path:
    file_name = get_product_file_name(config)
    return product_workflow_folder(config) / Path(f"{workflow_type}_{file_name}").with_suffix(".py")


def eval_pydantic_forms_version() -> bool:
    updated_version = semver.Version.parse("2.0.0")

    installed_version = metadata.version("pydantic-forms")
    installed_semver = semver.Version.parse(installed_version)

    return installed_semver >= updated_version


def render_template(environment: Environment, config: dict, template: str, workflow: str = "") -> str:
    use_updated_readonly_field = eval_pydantic_forms_version()
    product_block = root_product_block(config)
    types_to_import = get_name_spaced_types_to_import(product_block["fields"])
    fields = get_input_fields(product_block)
    constrained_ints = get_constrained_ints(fields)
    int_enums = get_int_enums(fields)
    str_enums = get_str_enums(fields)
    fields = merge_fields(fields, int_enums, str_enums)
    product_block_types = constrained_ints + int_enums + str_enums
    validations, validation_imports = get_validations(fields, workflow)
    existing_product_blocks = get_existing_product_blocks()

    if workflow:
        workflow_config = get_workflow(config, workflow)
        workflow_validations = workflow_config.get("validations", [])

    return environment.get_template(template).render(
        product=config,
        product_block=product_block,
        fields=fields,
        validations=validations,
        validation_imports=validation_imports,
        types_to_import=types_to_import,
        product_block_types=product_block_types,
        existing_product_blocks=existing_product_blocks,
        product_blocks_module=get_product_blocks_module(),
        product_types_module=get_product_types_module(),
        workflows_module=get_workflows_module(),
        workflow_validations=workflow_validations if workflow else [],
        use_updated_readonly_field=use_updated_readonly_field,
    )


def generate_shared_workflow_files(environment: Environment, config: dict, writer: Callable) -> None:
    content = render_template(environment, config, "shared_forms.j2")
    path = shared_product_workflow_folder(config) / Path("forms.py")
    writer(path, content)

    template = environment.get_template("shared_workflows.j2")
    content = template.render()
    path = get_workflows_folder() / Path("shared.py")
    writer(path, content)


def generate_workflow(f: Callable | None = None, workflow: str | None = None) -> Callable:
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
    content = render_template(environment, config, "create_product.j2", "create")
    path = get_product_workflow_path(config, "create")
    writer(path, content)


@generate_workflow(workflow="modify")
def generate_modify_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    content = render_template(environment, config, "modify_product.j2", "modify")
    path = get_product_workflow_path(config, "modify")
    writer(path, content)


@generate_workflow(workflow="validate")
def generate_validate_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    content = render_template(environment, config, "validate_product.j2", "validate")
    path = get_product_workflow_path(config, "validate")
    writer(path, content)


@generate_workflow(workflow="terminate")
def generate_terminate_workflow(environment: Environment, config: dict, writer: Callable) -> None:
    content = render_template(environment, config, "terminate_product.j2", "terminate")
    path = get_product_workflow_path(config, "terminate")
    writer(path, content)

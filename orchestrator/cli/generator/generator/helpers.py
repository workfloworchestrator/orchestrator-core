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
from collections.abc import Generator
from pathlib import Path

import structlog
from more_itertools import first

from orchestrator.cli.generator.generator.enums import to_dict
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings
from orchestrator.utils.helpers import camel_to_snake, snake_to_camel

logger = structlog.getLogger(__name__)


def get_workflow(config: dict, workflow_name: str) -> dict:
    workflows = (workflow for workflow in config.get("workflows", []) if workflow["name"] == workflow_name)
    return first(workflows, {})


def get_variable(config: dict) -> str:
    return config.get("variable", camel_to_snake(config["name"]))


def get_product_block_variable(product_block: dict) -> str:
    return get_variable(product_block)


def get_product_file_name(config: dict) -> str:
    return get_variable(config)


def get_product_block_file_name(product_block: dict) -> str:
    return get_product_block_variable(product_block)


def root_product_block(config: dict) -> dict:
    product_blocks = config.get("product_blocks", [])
    # TODO: multiple product_blocks will need more logic, ok for now
    return product_blocks[0]


def insert_into_imports(content: list[str], new_import: str) -> list[str]:
    # Note: we may consider using a real Python parser here someday, but for now this is ok and formatting
    # gets done by isort and black.
    def produce() -> Generator:
        not_inserted_yet = True
        for line in content:
            if line.startswith("from ") and not_inserted_yet:
                yield new_import
                not_inserted_yet = False
            yield line

    return list(produce())


def path_to_module(path: Path) -> str:
    return str(path).replace("/", ".")


def get_workflows_folder() -> Path:
    return settings.FOLDER_PREFIX / settings.WORKFLOWS_PATH


def get_product_blocks_folder() -> Path:
    return settings.FOLDER_PREFIX / settings.PRODUCT_BLOCKS_PATH


def get_product_types_folder() -> Path:
    return settings.FOLDER_PREFIX / settings.PRODUCT_TYPES_PATH


def get_workflows_module() -> str:
    return path_to_module(get_workflows_folder())


def get_product_blocks_module() -> str:
    return path_to_module(get_product_blocks_folder())


def get_product_types_module() -> str:
    return path_to_module(get_product_types_folder())


def get_product_path(config: dict) -> Path:
    file_name = get_product_file_name(config)
    return get_product_types_folder() / Path(file_name).with_suffix(".py")


def get_product_import(product: dict, lifecycle: str = "") -> str:
    return f'from {get_product_types_module()}.{product["variable"]} import {product["type"]}{lifecycle}\n'


def create_dunder_init_files(path: Path) -> None:
    folder = Path("")
    for part in path.parts:
        if (folder := folder / part).is_dir():
            if not (dunder_init_file := folder / Path("__init__.py")).exists():
                logger.info("creating missing dunder init", path=str(dunder_init_file))
                open(dunder_init_file, "x").close()


def is_constrained_int(field: dict) -> bool:
    return "min_value" in field or "max_value" in field


def get_constrained_ints(fields: list[dict]) -> list[dict]:
    return [field for field in fields if is_constrained_int(field)]


def merge_fields(fields: list[dict], int_enums: list[dict], str_enums: list[dict]) -> list[dict]:
    return list((to_dict(fields) | to_dict(int_enums) | to_dict(str_enums)).values())


def is_name_spaced_field_type(field: dict) -> bool:
    return "." in field["type"]


def name_space_get_type(name_spaced_type: str) -> str:
    return name_spaced_type.split(".")[-1]


def process_fields(fields: list[dict]) -> list[dict]:
    def to_type(field: dict) -> dict:
        if is_constrained_int(field):
            return field | {"type": snake_to_camel(field["name"])}

        if is_name_spaced_field_type(field):
            return field | {"type": name_space_get_type(field["type"])}

        return field

    return [to_type(field) for field in fields]


def get_all_fields(product_block: dict) -> list[dict]:
    return process_fields(product_block["fields"])


def get_input_fields(product_block: dict) -> list[dict]:
    def supported_input_type(field: dict) -> bool:
        return field["type"] in ("int", "str", "bool", "enum")

    return process_fields([field for field in product_block["fields"] if supported_input_type(field)])


def get_name_spaced_types_to_import(fields: list) -> list[tuple]:
    # NOTE: we could make this smarter by grouping imports from the namespace, but isort will handle this for us
    def name_space_split(field: dict) -> tuple[str, str]:
        *namespace, type = field["type"].split(".")
        return ".".join(namespace), type

    return [name_space_split(field) for field in fields if is_name_spaced_field_type(field)]

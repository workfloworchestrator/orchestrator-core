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
from more_itertools import first, one

from orchestrator.cli.generator.generator.settings import product_generator_settings as settings
from orchestrator.utils.helpers import camel_to_snake

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
    return one(product_blocks)


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


def get_product_types_module() -> str:
    return path_to_module(settings.FOLDER_PREFIX / settings.PRODUCT_TYPES_PATH)


def get_product_import(product: dict, lifecycle: str = "") -> str:
    return f'from {get_product_types_module()}.{product["variable"]} import {product["type"]}{lifecycle}\n'


def create_dunder_init_files(path: Path) -> None:
    folder = Path("")
    for part in path.parts:
        if (folder := folder / part).is_dir():
            if not (dunder_init_file := folder / Path("__init__.py")).exists():
                logger.info("creating missing dunder init", path=str(dunder_init_file))
                open(dunder_init_file, "x").close()

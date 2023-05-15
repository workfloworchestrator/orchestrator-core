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

from more_itertools import first, one

from orchestrator.cli.generator.generator.settings import product_generator_settings


def snake_to_camel(s: str) -> str:
    return "".join(x.title() for x in s.split("_"))


def get_workflow(config: dict, workflow_name: str) -> dict:
    workflows = (workflow for workflow in config.get("workflows", []) if workflow["name"] == workflow_name)
    return first(workflows, {})


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


def path_to_module(path: str) -> str:
    return path.replace("/", ".")


product_types_module = path_to_module(product_generator_settings.PRODUCT_TYPES_PATH)


def get_product_import(product: dict, lifecycle: str = "") -> str:
    return f'from {product_types_module}.{product["variable"]} import {product["type"]}{lifecycle}\n'

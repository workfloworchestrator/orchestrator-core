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

import inspect
from collections.abc import Generator
from importlib import import_module
from os import listdir
from typing import Any, Dict, List

from orchestrator.cli.generator.generator.helpers import snake_to_camel
from orchestrator.cli.generator.generator.settings import product_generator_settings
from orchestrator.domain.base import ProductBlockModel


def get_existing_product_blocks() -> Dict[str, Any]:
    def yield_blocks() -> Generator:
        def is_product_block(attribute: Any) -> bool:
            return issubclass(attribute, ProductBlockModel)

        for pb_file in listdir(product_generator_settings.PRODUCT_BLOCKS_PATH):
            name = pb_file.removesuffix(".py")
            module_name = f"surf.products.product_blocks.{name}"

            module = import_module(module_name)

            classes = [obj for _, obj in inspect.getmembers(module, inspect.isclass) if obj.__module__ == module_name]

            for klass in classes:
                if is_product_block(klass):
                    yield klass.__name__, module_name

    return dict(yield_blocks())


def is_restrained_int(field: dict) -> bool:
    return "min_value" in field or "max_value" in field


def is_name_spaced_field_type(field: dict) -> bool:
    return "." in field["type"]


def name_space_get_type(name_spaced_type: str) -> str:
    return name_spaced_type.split(".")[-1]


def get_fields(product_block: Dict) -> list[Dict]:
    def to_type(field: Dict) -> Dict:
        if is_restrained_int(field):
            return field | {"type": snake_to_camel(field["name"])}
        elif is_name_spaced_field_type(field):
            return field | {"type": name_space_get_type(field["type"])}
        else:
            return field

    return [to_type(field) for field in product_block["fields"]]


def get_lists_to_generate(fields: list[dict]) -> list[dict]:
    return [field for field in fields if field["type"] == "list"]


def get_name_spaced_types_to_import(fields: list) -> list[tuple]:
    # NOTE: we could make this smarter by grouping imports from the namespace, but isort will handle this for us
    def name_space_split(field: dict) -> tuple[str, str]:
        *namespace, type = field["type"].split(".")
        return ".".join(namespace), type

    return [name_space_split(field) for field in fields if is_name_spaced_field_type(field)]


def get_product_blocks_to_import(lists_to_generate: List, existing_product_blocks: Dict) -> list[tuple]:
    return [
        (module, lt["list_type"])
        for lt in lists_to_generate
        if (module := existing_product_blocks.get(f'{lt["list_type"]}Block'))
    ]


def generate_product_blocks(context: Dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    template = environment.get_template("product_block.j2")

    existing_product_blocks = get_existing_product_blocks()

    def generate_product_block(product_block: dict) -> None:
        types_to_import = get_name_spaced_types_to_import(product_block["fields"])

        fields = get_fields(product_block)

        lists_to_generate = get_lists_to_generate(fields)

        product_blocks_to_import = get_product_blocks_to_import(lists_to_generate, existing_product_blocks)

        restrained_ints_to_generate = [field for field in fields if is_restrained_int(field)]

        content = template.render(
            lists_to_generate=lists_to_generate,
            product_block=product_block | {"fields": fields},
            product_blocks_to_import=product_blocks_to_import,
            restrained_ints_to_generate=restrained_ints_to_generate,
            types_to_import=types_to_import,
        )

        file_name = product_block["variable"]
        path = f"{product_generator_settings.PRODUCT_BLOCKS_PATH}/{file_name}.py"

        writer(path, content)

    product_blocks = config.get("product_blocks", [])
    for product_block in product_blocks:
        generate_product_block(product_block)

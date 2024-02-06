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
import re
from collections.abc import Generator
from importlib import import_module
from os import listdir, path
from pathlib import Path
from typing import Any

import structlog

from orchestrator.cli.generator.generator.enums import get_int_enums, get_str_enums
from orchestrator.cli.generator.generator.helpers import (
    create_dunder_init_files,
    get_all_fields,
    get_constrained_ints,
    get_name_spaced_types_to_import,
    get_product_block_file_name,
    get_product_blocks_folder,
    get_product_blocks_module,
    merge_fields,
)
from orchestrator.domain.base import ProductBlockModel

logger = structlog.getLogger(__name__)


def get_existing_product_blocks() -> dict[str, Any]:
    def yield_blocks() -> Generator:
        def is_product_block(attribute: Any) -> bool:
            return issubclass(attribute, ProductBlockModel)

        if not path.exists(get_product_blocks_folder()):
            logger.warning("Product block path does not exist", product_blocks_path=get_product_blocks_folder())
            return

        for pb_file in listdir(get_product_blocks_folder()):
            name = pb_file.removesuffix(".py")
            module_name = f"{get_product_blocks_module()}.{name}"

            module = import_module(module_name)

            classes = [obj for _, obj in inspect.getmembers(module, inspect.isclass) if obj.__module__ == module_name]

            for klass in classes:
                if is_product_block(klass):
                    yield klass.__name__, module_name

    return dict(yield_blocks())


def get_lists_to_generate(fields: list[dict]) -> list[dict]:
    def should_generate(type: str, list_type: str | None = None, **kwargs: Any) -> bool:
        return type == "list" and list_type not in ["str", "int", "bool", "UUID"]

    return [field for field in fields if should_generate(**field)]


def get_product_blocks_to_import(label: str, fields: list, existing_product_blocks: dict) -> list[tuple]:
    return [
        (module, field[label]) for field in fields if (module := existing_product_blocks.get(f"{field[label]}Block"))
    ]


def get_product_block_path(product_block: dict) -> Path:
    file_name = get_product_block_file_name(product_block)
    return get_product_blocks_folder() / Path(file_name).with_suffix(".py")


def enrich_product_block(product_block: dict) -> dict:
    def to_block_name() -> str:
        type = product_block["type"]
        name = re.sub("(.)([A-Z][a-z]+)", r"\1 \2", type)
        return re.sub("([a-z0-9])([A-Z])", r"\1 \2", name)

    fields = get_all_fields(product_block)
    block_name = product_block.get("block_name", to_block_name())

    return product_block | {
        "fields": fields,
        "block_name": block_name,
    }


def generate_product_blocks(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]
    python_version = context["python_version"]

    template = environment.get_template("product_block.j2")

    existing_product_blocks = get_existing_product_blocks()

    def generate_product_block(product_block: dict) -> None:
        types_to_import = get_name_spaced_types_to_import(product_block["fields"])

        fields = get_all_fields(product_block)

        int_enums = get_int_enums(fields)
        str_enums = get_str_enums(fields)

        lists_to_generate = get_lists_to_generate(fields)

        product_blocks_to_import = list(
            set(
                get_product_blocks_to_import("list_type", lists_to_generate, existing_product_blocks)
                + get_product_blocks_to_import("type", fields, existing_product_blocks)
            )
        )
        product_block_types = [type for module, type in product_blocks_to_import]
        constrained_ints_to_generate = get_constrained_ints(fields)
        fields = merge_fields(fields, int_enums, str_enums)

        path = get_product_block_path(product_block)
        content = template.render(
            lists_to_generate=lists_to_generate,
            product_block=enrich_product_block(product_block),
            product_blocks_to_import=product_blocks_to_import,
            product_block_types=product_block_types,
            constrained_ints_to_generate=constrained_ints_to_generate,
            types_to_import=types_to_import,
            python_version=python_version,
            int_enums=int_enums,
            str_enums=str_enums,
            fields=fields,
        )

        writer(path, content)

    product_blocks = config.get("product_blocks", [])
    for product_block in product_blocks:
        generate_product_block(product_block)
    create_dunder_init_files(get_product_blocks_folder())

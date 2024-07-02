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
import itertools
import re
import subprocess  # noqa: S404
from collections.abc import Callable, Generator
from datetime import datetime
from os import environ
from pathlib import Path
from typing import Any

import structlog
from alembic.util import rev_id
from jinja2 import Environment

from orchestrator.cli.generator.generator.helpers import (
    find_root_product_block,
    get_product_block_depends_on,
    get_product_types_module,
    set_resource_types,
    sort_product_blocks_by_dependencies,
)
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings
from orchestrator.settings import convert_database_uri

logger = structlog.getLogger(__name__)


def create_migration_file(message: str, head: str) -> Path | None:
    if environ.get("DATABASE_URI"):
        environ.update({"DATABASE_URI": convert_database_uri(environ["DATABASE_URI"])})
    else:
        environ.update({"DATABASE_URI": "postgresql+psycopg://nwa:nwa@localhost/orchestrator-core"})
    if not environ.get("PYTHONPATH"):
        environ.update({"PYTHONPATH": "."})
    logger.info(
        "creating new db revision", database_uri=environ.get("DATABASE_URI"), pythonpath=environ.get("PYTHONPATH")
    )
    create_migration_command = f'python main.py db revision --message "{message}" --head={head}@head'
    result = subprocess.check_output(create_migration_command, shell=True, text=True)  # noqa: S602

    for line in result.splitlines():
        if m := re.search("migrations/versions/schema/([^ ]+)", line):
            return Path("migrations/versions/schema") / m[1]
    else:
        return None


def get_revisions(result: str) -> dict[str, str]:
    def is_revision(line: str) -> Any:
        match = re.search("^([^ ]+) \\(([^ ]+)\\)", line)
        return reversed(match.groups()) if match else None

    return dict(revision for line in result.splitlines() if (revision := is_revision(line)))


def get_heads() -> dict:
    get_heads_command = "python main.py db heads"
    result = subprocess.check_output(get_heads_command, shell=True, text=True)  # noqa: S602
    return get_revisions(result)


def create_data_head(context: dict, depends_on: str) -> None:
    environment = context["environment"]
    writer = context["writer"]

    create_date = datetime.now()
    revision = rev_id()
    template = environment.get_template("create_data_head.j2")
    path = Path("migrations/versions/schema") / f"{str(create_date.date())}_{revision}_create_data_head.py"
    content = template.render(create_date=create_date.isoformat(), depends_on=depends_on, revision=revision)
    writer(path, content)


def extract_revision_info(content: list[str]) -> dict:
    def process() -> Generator:
        for line in content:
            if m := re.search("Revision ID: (.+)", line):
                yield "revision", m[1]
            if m := re.search("Revises: (.+)", line):
                yield "down_revision", m[1]
            if m := re.search("Create Date: (.+)", line):
                yield "create_date", m[1]

    return dict(process())


def update_subscription_model_registry(
    environment: Environment,
    config: dict,
    product_variants: list[tuple[Any, Any]],
    writer: Callable,
) -> None:
    template = environment.get_template("subscription_model_registry.j2")
    product_variable = config.get("variable", "")
    product_type = config.get("type", "")
    content = template.render(
        product=config, product_variants=product_variants, product_types_module=get_product_types_module()
    )

    path = settings.FOLDER_PREFIX / settings.PRODUCT_REGISTRY_PATH
    with open(path) as fp:
        import_statement = (
            "from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY\n"
            if "SUBSCRIPTION_MODEL_REGISTRY" not in fp.read()
            else ""
        )
    with open(path) as fp:
        if f"from {get_product_types_module()}.{product_variable} import {product_type}" not in fp.read():
            fp.close()
            writer(path, import_statement + content, append=True)
        else:
            logger.warning("not re-updating subscription model registry", product=product_type)


def get_revision_info(migration_file: Path) -> dict:
    try:
        with open(migration_file) as stream:
            original_content = stream.readlines()
    except FileNotFoundError:
        logger.error("Migration file not found", path=str(migration_file))
        return {}
    else:
        return extract_revision_info(original_content)


def generate_product_migration(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    heads = get_heads()
    if "data" not in heads:
        create_data_head(context=context, depends_on=heads["schema"])

    if not (migration_file := create_migration_file(message=f"add {config['name']}", head="data")):
        logger.error("Could not create migration file")
        return

    if not (revision_info := get_revision_info(migration_file)):
        logger.error("Could not get revision info from migration file", migration_file=migration_file)
        return

    if fixed_inputs := config.get("fixed_inputs"):
        fixed_input_values = [
            [(fixed_input["name"], str(value)) for value in fixed_input["values"]]
            for fixed_input in fixed_inputs
            if "values" in fixed_input
        ]
        fixed_input_combinations = list(itertools.product(*fixed_input_values))
        product_variants = [
            (" ".join([config["name"]] + [value for name, value in combination]), combination)
            for combination in fixed_input_combinations
        ]
    else:
        product_variants = [((config["name"]), ())]

    # Add depends_on_block_relations, sort the product blocks, set resource types and the root block
    product_blocks = sort_product_blocks_by_dependencies(config.get("product_blocks", []))
    block_depends_on = get_product_block_depends_on(product_blocks, include_existing_blocks=True)
    config["root_product_block"] = find_root_product_block(product_blocks)
    product_blocks = set_resource_types(product_blocks, block_depends_on)

    for block in product_blocks:
        block["depends_on_blocks"] = block_depends_on[block["type"]]

    template = environment.get_template("new_product_migration.j2")
    config["product_blocks"] = product_blocks
    content = template.render(product=config, product_variants=product_variants, **revision_info)
    writer(migration_file, content)
    update_subscription_model_registry(environment, config, product_variants, writer)

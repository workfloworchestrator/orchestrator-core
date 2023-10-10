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
import re
import subprocess  # noqa: S404
from os import environ
from pathlib import Path
from typing import Generator, Optional

import structlog

logger = structlog.getLogger(__name__)


def create_migration_file(config: dict) -> Optional[str]:
    if not environ.get("DATABASE_URI"):
        environ.update({"DATABASE_URI": "postgresql://nwa:nwa@localhost/orchestrator-core"})
    if not environ.get("PYTHONPATH"):
        environ.update({"PYTHONPATH": "."})
    logger.info(
        "creating new db revision", database_uri=environ.get("DATABASE_URI"), pythonpath=environ.get("PYTHONPATH")
    )
    create_migration_command = f'python main.py db revision --message "Add {config["name"]}" --head=data@head'
    result = subprocess.check_output(create_migration_command, shell=True, text=True)  # noqa: S602

    for line in result.splitlines():
        if m := re.search("migrations/versions/schema/([^ ]+)", line):
            return m[1]
    else:
        return None


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


def generate_product_migration(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    if migration_file := create_migration_file(config):
        path = Path("migrations/versions/schema") / Path(migration_file)
        try:
            with open(path) as stream:
                original_content = stream.readlines()
        except FileNotFoundError:
            logger.error("Migration file not found", path=str(path))
        else:
            revision_info = extract_revision_info(original_content)

            template = environment.get_template("new_product_migration.j2")
            content = template.render(product=config, **revision_info)

            writer(path, content)

    else:
        logger.error("Could not create migration file")

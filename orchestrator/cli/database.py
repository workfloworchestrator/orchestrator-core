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

import os
from shutil import copyfile
from typing import List, Optional

import jinja2
import typer
from alembic import command
from alembic.config import Config
from structlog import get_logger

import orchestrator

logger = get_logger(__name__)

app: typer.Typer = typer.Typer()

orchestrator_module_location = os.path.dirname(orchestrator.__file__)
migration_dir = "migrations"

loader = jinja2.FileSystemLoader(os.path.join(orchestrator_module_location, f"{migration_dir}/templates"))
jinja_env = jinja2.Environment(
    loader=loader, autoescape=True, lstrip_blocks=True, trim_blocks=True, undefined=jinja2.StrictUndefined
)


def alembic_cfg() -> Config:
    cfg = Config("alembic.ini")
    version_locations = cfg.get_main_option("version_locations")
    cfg.set_main_option(
        "version_locations", f"{version_locations} {orchestrator_module_location}/{migration_dir}/versions/schema"
    )
    logger.info("Version Locations", locations=cfg.get_main_option("version_locations"))
    return cfg


@app.command(
    help="Initialize an empty migrations environment. This command will throw an exception when it detects conflicting files and directories."
)
def init() -> None:
    """
    Initialise the migrations directory.

    This command will initialize a migration directory for the orchestrator core application and setup a correct
    migration environment.

    Returns:
        None

    """

    if os.access(migration_dir, os.F_OK) and os.listdir(migration_dir):
        raise OSError(f"Directory {migration_dir} already exists and is not empty")

    logger.info("Creating directory", directory=os.path.abspath(migration_dir))
    os.makedirs(migration_dir)
    versions = os.path.join(migration_dir, "versions")
    logger.info("Creating directory", directory=os.path.abspath(versions))
    os.makedirs(versions)
    versions_schema = os.path.join(migration_dir, "versions/schema")
    logger.info("Creating directory", directory=os.path.abspath(versions_schema))
    os.makedirs(versions_schema)

    source_env_py = os.path.join(orchestrator_module_location, f"{migration_dir}/templates/env.py.j2")
    env_py = os.path.join(migration_dir, "env.py")
    logger.info("Creating file", file=os.path.abspath(env_py))
    copyfile(source_env_py, env_py)

    source_script_py_mako = os.path.join(orchestrator_module_location, f"{migration_dir}/script.py.mako")
    script_py_mako = os.path.join(migration_dir, "script.py.mako")
    logger.info("Creating file", file=os.path.abspath(script_py_mako))
    copyfile(source_script_py_mako, script_py_mako)

    source_helpers_py = os.path.join(orchestrator_module_location, f"{migration_dir}/templates/helpers.py.j2")
    helpers_py = os.path.join(migration_dir, "helpers.py")
    logger.info("Creating file", file=os.path.abspath(helpers_py))
    copyfile(source_helpers_py, helpers_py)

    template = jinja_env.get_template("alembic.ini.j2")

    if not os.access(os.path.join(os.getcwd(), "alembic.ini"), os.F_OK):
        logger.info("Creating file", file=os.path.join(os.getcwd(), "alembic.ini"))
        with open(os.path.join(os.getcwd(), "alembic.ini"), "w") as alembic_ini:
            alembic_ini.write(template.render(migrations_dir=migration_dir))
    else:
        logger.info("Skipping Alembic.ini file. It already exists")


@app.command(help="Get the database heads")
def heads() -> None:
    command.heads(alembic_cfg())


@app.command(help="Merge database revisions.")
def merge(
    revisions: Optional[List[str]] = typer.Argument(
        None, help="Add the revision you would like to merge to this command."
    ),
    message: str = typer.Option(None, "--message", "-m", help="The revision message"),
) -> None:
    """
    Merge database revisions.

    Args:
        revisions: List of revisions to merge
        message: Optional message for the revision.

    Returns:
        None

    """
    command.merge(alembic_cfg(), revisions, message=message)


@app.command()
def upgrade(revision: Optional[str] = typer.Argument(None, help="Rev id to upgrade to")) -> None:
    """
    Upgrade the database.

    Args:
        revision: Optional argument to indicate where to upgrade to.

    Returns:
        None

    """
    command.upgrade(alembic_cfg(), revision)


@app.command()
def downgrade(revision: Optional[str] = typer.Argument(None, help="Rev id to upgrade to")) -> None:
    """
    Downgrade the database.

    Args:
        revision: Optional argument to indicate where to downgrade to.

    Returns:
        None

    """
    command.downgrade(alembic_cfg(), revision)


@app.command()
def revision(
    message: str = typer.Option(None, "--message", "-m", help="The revision message"),
    autogenerate: bool = typer.Option(False, help="Detect schema changes and add migrations"),
    head: str = typer.Option(None, help="Determine the head the head you need to add your migration to."),
) -> None:
    """
    Create a new revision file.

    Args:
        message: The revision message
        autogenerate: Whether to detect schema changes.
        head: To which head the migration applies

    Returns:
        None

    """
    command.revision(alembic_cfg(), message, autogenerate=autogenerate, head=head)

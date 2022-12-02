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

import json
import os
import re
from shutil import copyfile
from typing import Any, List, Optional, Tuple, Union

import jinja2
import typer
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from structlog import get_logger

import orchestrator
from orchestrator.cli.domain_gen_helpers.types import ModelUpdates
from orchestrator.cli.migrate_domain_models import create_domain_models_migration_sql
from orchestrator.db import init_database
from orchestrator.settings import app_settings

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
    version_path: str = typer.Option(None, "--version-path", help="Specify specific path from config for version file"),
    autogenerate: bool = typer.Option(False, help="Detect schema changes and add migrations"),
    head: str = typer.Option(None, help="Determine the head the head you need to add your migration to."),
) -> None:
    """
    Create a new revision file.

    Args:
        message: The revision message
        version_path: Specify specific path from config for version file
        autogenerate: Whether to detect schema changes.
        head: To which head the migration applies

    Returns:
        None

    """
    command.revision(alembic_cfg(), message, version_path=version_path, autogenerate=autogenerate, head=head)


@app.command()
def history(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    indicate_current: bool = typer.Option(False, "--current", "-c", help="Indicate current revision"),
) -> None:
    """
    List changeset scripts in chronological order.

    Args:
        verbose: Verbose output
        indicate_current: Indicate current revision

    Returns:
        None

    """
    command.history(alembic_cfg(), verbose=verbose, indicate_current=indicate_current)


def remove_down_revision_from_text(text: str) -> str:
    r"""Remove down revision from text.

    >>> text = "Revises: bed6bc0b197a"
    >>> remove_down_revision_from_text(text)
    'Revises:'

    >>> text = "down_revision = 'bed6bc0b197a'"
    >>> remove_down_revision_from_text(text)
    'down_revision = None'

    >>> text = "initial\n\nRevises: bed6bc0b197a\n\ndown_revision = 'bed6bc0b197a'\n\ntesting"
    >>> remove_down_revision_from_text(text)
    'initial\n\nRevises:\n\ndown_revision = None\n\ntesting'

    >>> text = "initial\n\nRevises: bed6bc0b197a\n\ndown_revision='bed6bc0b197a'\n\ntesting"
    >>> remove_down_revision_from_text(text)
    "initial\n\nRevises:\n\ndown_revision='bed6bc0b197a'\n\ntesting"

    """
    text = re.sub(r"Revises: [0-9a-z]+", r"Revises:", text, count=1)
    return re.sub(r"down_revision = ['\"][0-9a-z]+['\"]", r"down_revision = None", text, count=1)


def remove_core_as_down_revision(migration: Any) -> None:
    with open(migration.path) as f:
        text = f.read()

    text = remove_down_revision_from_text(text)

    with open(migration.path, "w") as f:
        f.write(text)


@app.command(help="Create revision based on diff_product_in_database.")
def migrate_domain_models(
    message: str = typer.Argument(..., help="Migration name"),
    test: Optional[bool] = typer.Option(False, help="Optional boolean if you don't want to generate a migration file"),
    inputs: Optional[str] = typer.Option("{}", help="stringified dict to prefill inputs"),
    updates: Optional[str] = typer.Option("{}", help="stringified dict to map updates instead of using inputs"),
) -> Union[Tuple[List[str], List[str]], None]:
    """Create migration file based on SubscriptionModel.diff_product_in_database. BACKUP DATABASE BEFORE USING THE MIGRATION!.

    You will be prompted with inputs for new models and resource type updates.
    Resource type updates are only handled when it's renamed in all product blocks.

    Args:
    - `message`: Message/description of the generated migration.
    - `--test`: Optional boolean if you don't want to generate a migration file.
    - `--inputs`: stringified dict to prefill inputs.
        The inputs and updates argument is mostly used for testing, prefilling the given inputs, here examples:
        - new product: `inputs = { "new_product_name": { "description": "add description", "product_type": "add_type", "tag": "add_tag" }}`
        - new product fixed input: `inputs = { "new_product_name": { "new_fixed_input_name": "value" }}`
        - new product block: `inputs = { "new_product_block_name": { "description": "add description", "tag": "add_tag" } }`
        - new resource type: `inputs = { "new_resource_type_name": { "description": "add description", "value": "add default value", "new_product_block_name": "add default value for block" }}`
            - `new_product_block_name` prop inserts value specifically for that block.
            - `value` prop is inserted as default for all existing instances it is added to.

    - `--updates`: stringified dict to prefill inputs.
        - renaming a fixed input:
            - `updates = { "fixed_inputs": { "product_name": { "old_fixed_input_name": "new_fixed_input_name" } } }`
        - renaming a resource type to a new resource type:
            - `inputs = { "new_resource_type_name": { "description": "add description" }}`
            - `updates = { "resource_types": { "old_resource_type_name": "new_resource_type_name" } }`
        - renaming a resource type to existing resource type: `updates = { "resource_types": { "old_resource_type_name": "new_resource_type_name" } }`

    Returns None unless `--test` is used, in which case it returns:
        - tuple:
            - list of upgrade SQL statements in string format.
            - list of downgrade SQL statements in string format.
    """
    if not app_settings.TESTING:
        init_database(app_settings)

    inputs_dict = json.loads(inputs) if isinstance(inputs, str) else {}
    updates_dict = json.loads(updates) if isinstance(updates, str) else {}
    updates_class = None
    if updates_dict:
        updates_class = ModelUpdates(
            fixed_inputs=updates_dict.get("fixed_inputs", {}),
            resource_types=updates_dict.get("resource_types", {}),
        )
    sql_upgrade_stmts, sql_downgrade_stmts = create_domain_models_migration_sql(inputs_dict, updates_class, bool(test))

    if test:
        print("--- TEST DOES NOT GENERATE SQL MIGRATION ---")  # noqa: T001, T201
        return sql_upgrade_stmts, sql_downgrade_stmts

    print("--- GENERATING SQL MIGRATION FILE ---")  # noqa: T001, T201

    sql_upgrade_str = "\n".join([f'    conn.execute("""\n{sql_stmt}\n    """)' for sql_stmt in sql_upgrade_stmts])
    sql_downgrade_str = "\n".join([f'    conn.execute("""\n{sql_stmt}\n    """)' for sql_stmt in sql_downgrade_stmts])

    alembic_config = alembic_cfg()
    non_venv_location = " ".join(
        [
            location
            for location in alembic_config.get_main_option("version_locations").split(" ")
            if "site-packages" not in location
        ]
    )

    try:
        # Initial alembic migration generate that doesn't know about a branch 'data' and remove core down revision.
        script = ScriptDirectory.from_config(alembic_config)
        core_head = script.get_current_head()
        migration = command.revision(
            alembic_config,
            message,
            branch_label="data",
            version_path=non_venv_location,
            depends_on=core_head,
        )

        remove_core_as_down_revision(migration)
    except CommandError as err:
        error_str = str(err)
        if ("Branch name 'data'" in error_str and "already used by revision" in error_str) or (
            "The script directory has multiple heads" in error_str
        ):
            try:
                migration = command.revision(alembic_config, message, head="data@head", version_path=non_venv_location)
            except CommandError:
                if "Branch name 'data'" in error_str and "already used by revision" in error_str:
                    raise CommandError("Database not up to date with latest revision")
                else:
                    raise CommandError("Database head 'data' already exists but no revision/migration file found")
        else:
            raise err

    with open(migration.path) as f:
        file_data = f.read()

    new_file_data = file_data.replace("    pass", f"    conn = op.get_bind()\n{sql_upgrade_str}", 1)
    new_file_data = new_file_data.replace("    pass", f"    conn = op.get_bind()\n{sql_downgrade_str}", 1)
    with open(migration.path, "w") as f:
        f.write(new_file_data)

    print("--- MIGRATION GENERATED (DON'T FORGET TO BACKUP DATABASE BEFORE MIGRATING!) ---")  # noqa: T001, T201
    return None

# Copyright 2019-2020 SURF, ESnet
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
from shutil import copyfile

import jinja2
import typer
from alembic import command
from alembic.config import Config
from structlog import get_logger

import orchestrator.workflows
from orchestrator.cli.domain_gen_helpers.types import ModelUpdates
from orchestrator.cli.helpers.print_helpers import COLOR, str_fmt
from orchestrator.cli.migrate_domain_models import create_domain_models_migration_sql
from orchestrator.cli.migrate_workflows import create_workflows_migration_wizard
from orchestrator.cli.migration_helpers import create_migration_file
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
    """Initialize the `migrations` directory.

    This command will initialize a migration directory for the orchestrator core application and setup a correct
    migration environment. It will also throw an exception when it detects conflicting files and directories.

    Returns:
        None

    CLI Options:
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
    """The `heads` command command shows the Alembic database heads.

    CLI Options:
        None

    """
    command.heads(alembic_cfg())  # type: ignore[no-untyped-call]


@app.command(help="Merge database revisions.")
def merge(
    revisions: str = typer.Argument(default=None, help="Add the revision you would like to merge to this command."),
    message: str = typer.Option(None, "--message", "-m", help="The revision message"),
) -> None:
    """Merge database revisions.

    It is possible when using multiple git branches in your WFO development lifecycle to have
    multiple Alembic heads emerge. This command will allow you to merge those two (or more)
    heads to resolve the issue. You also might need to run this after updating your version
    of orchestrator-core if there have been schema changes.

    [Read More Here](https://alembic.sqlalchemy.org/en/latest/branches.html#merging-branches)

    Args:
        revisions: List of revisions to merge
        message: Optional message for the revision.

    Returns:
        None

    CLI Options:
        ```sh
        Arguments:
            [REVISIONS]  Add the revision you would like to merge to this command.

        Options:
            -m, --message TEXT  The revision message
        ```
    """
    command.merge(alembic_cfg(), revisions, message=message)


@app.command()
def upgrade(revision: str = typer.Argument(help="Rev id to upgrade to")) -> None:
    """The `upgrade` command will upgrade the database to the specified revision.

    Args:
        revision: Optional argument to indicate where to upgrade to.

    Returns:
        None

    CLI Options:
        ```sh
        Arguments:
            [REVISION]  Rev id to upgrade to

        Options:
            --help  Show this message and exit.
        ```

    """
    command.upgrade(alembic_cfg(), revision)


@app.command()
def downgrade(revision: str = typer.Argument("-1", help="Rev id to downgrade to")) -> None:
    """The `downgrade` command will downgrade the database to the previous revision or to the optionally specified revision.

    Args:
        revision (str, optional): Optional argument to indicate where to downgrade to. [default: -1]

    Returns:
        None

    CLI Options:
        ```sh
        Arguments:
            [REVISION]  Rev id to upgrade to  [default: -1]
        ```

    """
    command.downgrade(alembic_cfg(), revision)


@app.command()
def revision(
    message: str = typer.Option(None, "--message", "-m", help="The revision message"),
    version_path: str = typer.Option(None, "--version-path", help="Specify specific path from config for version file"),
    autogenerate: bool = typer.Option(False, help="Detect schema changes and add migrations"),
    head: str = typer.Option(None, help="Determine the head you need to add your migration to."),
) -> None:
    """The `revision` command creates a new Alembic revision file.

    Args:
        message: The revision message
        version_path: Specify specific path from config for version file
        autogenerate: Whether to detect schema changes.
        head: To which head the migration applies

    Returns:
        None

    CLI Options:
        ```sh
        Options:
            -m, --message TEXT              The revision message
            --version-path TEXT             Specify specific path from config for version file
            --autogenerate / --no-autogenerate
                                            Detect schema changes and add migrations [default: no-autogenerate]
            --head TEXT                     Determine the head you need to add your migration to.
        ```
    """
    command.revision(alembic_cfg(), message, version_path=version_path, autogenerate=autogenerate, head=head)


@app.command()
def history(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    indicate_current: bool = typer.Option(True, "--current", "-c", help="Indicate current revision"),
) -> None:
    """The `history` command lists Alembic revision history/changeset scripts in chronological order.

    Args:
        verbose (bool, optional): Verbose output
        indicate_current (bool, optional): Indicate current revision

    Returns:
        None

    CLI Options:
        ```sh
        Options:
            -v, --verbose  Verbose output
            -c, --current  Indicate current revision
        ```
    """
    command.history(alembic_cfg(), verbose=verbose, indicate_current=indicate_current)


@app.command(help="Create revision based on diff_product_in_database.")
def migrate_domain_models(
    message: str = typer.Argument(..., help="Migration name"),
    test: bool = typer.Option(False, help="Optional boolean if you don't want to generate a migration file"),
    inputs: str = typer.Option("{}", help="Stringified dict to prefill inputs"),
    updates: str = typer.Option("{}", help="Stringified dict to map updates instead of using inputs"),
) -> tuple[list[str], list[str]] | None:
    """Create migration file based on SubscriptionModel.diff_product_in_database. BACKUP DATABASE BEFORE USING THE MIGRATION!.

    You will be prompted with inputs for new models and resource type updates.
    Resource type updates are only handled when it's renamed in all product blocks.

    Args:
        message: Message/description of the generated migration.
        test: Optional boolean if you don't want to generate a migration file.
        inputs: stringified dict to prefill inputs.
            The inputs and updates argument is mostly used for testing, prefilling the given inputs, here examples:
            - new product: `inputs = { "new_product_name": { "description": "add description", "product_type": "add_type", "tag": "add_tag" }}`
            - new product fixed input: `inputs = { "new_product_name": { "new_fixed_input_name": "value" }}`
            - new product block: `inputs = { "new_product_block_name": { "description": "add description", "tag": "add_tag" } }`
            - new resource type: `inputs = { "new_resource_type_name": { "description": "add description", "value": "add default value", "new_product_block_name": "add default value for block" }}`
                - `new_product_block_name` prop inserts value specifically for that block.
                - `value` prop is inserted as default for all existing instances it is added to.

        updates: stringified dict to prefill inputs.
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

    if test:
        print(  # noqa: T001, T201
            f"{str_fmt('NOTE:', flags=[COLOR.BOLD, COLOR.CYAN])} Running in test mode. No migration file will be generated.\n"
        )

    inputs_dict = json.loads(inputs) if isinstance(inputs, str) else {}
    updates_dict = json.loads(updates) if isinstance(updates, str) else {}
    updates_class = None
    if updates_dict:
        updates_class = ModelUpdates(
            fixed_inputs=updates_dict.get("fixed_inputs", {}),
            resource_types=updates_dict.get("resource_types", {}),
            block_resource_types=updates_dict.get("block_resource_types", {}),
        )
    sql_upgrade_stmts, sql_downgrade_stmts = create_domain_models_migration_sql(inputs_dict, updates_class, bool(test))

    if test:
        return sql_upgrade_stmts, sql_downgrade_stmts

    sql_upgrade_str = "\n".join(
        [f'    conn.execute(sa.text("""\n{sql_stmt}\n    """))' for sql_stmt in sql_upgrade_stmts]
    )
    sql_downgrade_str = "\n".join(
        [f'    conn.execute(sa.text("""\n{sql_stmt}\n    """))' for sql_stmt in sql_downgrade_stmts]
    )
    create_migration_file(alembic_cfg(), sql_upgrade_str, sql_downgrade_str, message)
    return None


@app.command(help="Create migration file based on diff workflows in db")
def migrate_workflows(
    message: str = typer.Argument(..., help="Migration name"),
    test: bool = typer.Option(False, help="Optional boolean if you don't want to generate a migration file"),
) -> tuple[list[dict], list[dict]] | None:
    """The `migrate-workflows` command creates a migration file based on the difference between workflows in the database and registered WorkflowInstances in your codebase.

    !!! warning "BACKUP YOUR DATABASE BEFORE USING THE MIGRATION!"

    You will be prompted with inputs for new models and resource type updates.
    Resource type updates are only handled when it's renamed in all product blocks.

    Args:
        message: Message/description of the generated migration.
        test: Optional boolean if you don't want to generate a migration file.

    Returns None unless `--test` is used, in which case it returns:
        - tuple:
            - list of upgrade SQL statements in string format.
            - list of downgrade SQL statements in string format.

    CLI Arguments:
        ```sh
        Arguments:
            MESSAGE  Migration name  [required]

        Options:
            --test / --no-test  Optional boolean if you don't want to generate a migration
            file  [default: no-test]
        ```
    """
    if not app_settings.TESTING:
        init_database(app_settings)

    if test:
        print(  # noqa: T001, T201
            f"{str_fmt('NOTE:', flags=[COLOR.BOLD, COLOR.CYAN])} Running in test mode. No migration file will be generated.\n"
        )

    workflows_to_add, workflows_to_delete = create_workflows_migration_wizard()

    # String 'template' arguments
    import_str = "from orchestrator.migrations.helpers import create_workflow, delete_workflow\n"
    tpl_preamble_lines = []
    tpl_upgrade_lines = []
    tpl_downgrade_lines = []

    if workflows_to_add:
        tpl_preamble_lines.append(f"new_workflows = {json.dumps(workflows_to_add, indent=4)}\n")
        tpl_upgrade_lines.extend(
            [(" " * 4) + "for workflow in new_workflows:", (" " * 8) + "create_workflow(conn, workflow)"]
        )
        tpl_downgrade_lines.extend(
            [(" " * 4) + "for workflow in new_workflows:", (" " * 8) + 'delete_workflow(conn, workflow["name"])']
        )

    if workflows_to_delete:
        tpl_preamble_lines.append(f"old_workflows = {json.dumps(workflows_to_delete, indent=4)}\n")
        tpl_upgrade_lines.extend(
            [(" " * 4) + "for workflow in old_workflows:", (" " * 8) + 'delete_workflow(conn, workflow["name"])']
        )
        tpl_downgrade_lines.extend(
            [(" " * 4) + "for workflow in old_workflows:", (" " * 8) + "create_workflow(conn, workflow)"]
        )

    preamble = "\n".join(
        [
            import_str,
            *tpl_preamble_lines,
        ]
    )
    sql_upgrade_str = "\n".join(tpl_upgrade_lines)
    sql_downgrade_str = "\n".join(tpl_downgrade_lines)

    if test:
        return workflows_to_add, workflows_to_delete

    create_migration_file(alembic_cfg(), sql_upgrade_str, sql_downgrade_str, message, preamble=preamble)
    return None

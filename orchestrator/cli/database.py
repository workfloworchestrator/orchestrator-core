import os
from pathlib import Path
from typing import Optional

import typer
from alembic import command
from alembic.config import Config
from alembic.util import CommandError
from structlog import get_logger

import orchestrator

logger = get_logger(__name__)

app: typer.Typer = typer.Typer()

this_location = os.path.join(os.path.dirname(os.path.realpath(__file__)))
orchestrator_module_location = os.path.dirname(orchestrator.__file__)
alembic_cfg = Config(file_=os.path.join(orchestrator_module_location, "migrations/alembic.ini"))


@app.command(name="upgrade")
def run_migrations(
    custom_migration_directory: Optional[Path] = typer.Option(None, help="The path towards the migration directory")
) -> None:
    """
    Run the migrations.

    This command will run the migrations for initialization of the database. If you have extra migrations that need to be run,
    add this to the

    Args:
        custom_migration_directory: Path to the migration directory.

    Returns:
        None

    """
    logger.info("Running migrations on the database", extra_migration_directory=str(custom_migration_directory))
    if custom_migration_directory:
        alembic_cfg.set_main_option(
            "version_locations",
            f"{os.path.join(orchestrator_module_location, 'migrations/versions/schema')}, {os.path.join(this_location)}/{custom_migration_directory}",
        )
    try:
        command.upgrade(alembic_cfg, "heads")
    except CommandError:
        logger.error(
            "Unable to run the migrations, no revisions found",
            path=f"{os.path.join(this_location)}/{custom_migration_directory}",
        )


@app.command(name="heads", help="List heads")
def list_heads() -> None:
    """
    List heads of the database.

    Returns:
        Heads of the database.

    """
    command.heads(alembic_cfg)


@app.command(name="downgrade", help="Downgrade database")
def downgrade(revision: Optional[str] = typer.Option(None, help="The revision to downgrade to")) -> None:
    """
    Downgrade the Database to a certain revision.

    Args:
        revision: The revision to downgrade to.

    Returns:
        None

    """
    command.downgrade(alembic_cfg, revision)


@app.command(name="migrate", help="Migrate the database")
def migrate(
    custom_migration_directory: Path = typer.Argument(..., help="The path towards the migration directory"),
    message: Optional[str] = typer.Option(None, help="The revision message"),
    autogenerate: Optional[bool] = typer.Option(
        False, help="Detect model changes and automatically generate migrations."
    ),
) -> None:
    """
    Migrate the database.

    Args:
        custom_migration_directory: The migration directory.
        message: The message of the migration
        autogenerate: whether to automatically generate schema change migrations.

    Returns:
        None

    """
    alembic_cfg.set_main_option(
        "version_locations",
        f"{os.path.join(orchestrator_module_location, 'migrations/versions/schema')}, {os.path.join(this_location)}/{custom_migration_directory}",
    )
    command.revision(alembic_cfg, message, autogenerate=autogenerate, version_path=custom_migration_directory)

import os
from shutil import copyfile

import jinja2
import typer
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


@app.command(name="init")
def init() -> None:
    """
    Run the migrations.

    This command will run the migrations for initialization of the database. If you have extra migrations that need to be run,
    add this to the

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

    source_env_py = os.path.join(orchestrator_module_location, f"{migration_dir}/env.py")
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
            alembic_ini.write(
                template.render(
                    migrations_dir=migration_dir,
                    module_migrations_dir=os.path.join(
                        orchestrator_module_location, f"{migration_dir}/versions/schema"
                    ),
                )
            )
    else:
        logger.info("Skipping Alembic.ini file. It already exists")

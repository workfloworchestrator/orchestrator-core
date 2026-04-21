import os
import re
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from structlog import get_logger

import orchestrator

logger = get_logger(__name__)

orchestrator_module_location = os.path.dirname(orchestrator.__file__)


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


def _insert_preamble(text: str, s: str) -> str:
    lines = text.splitlines(keepends=True)
    line_num = next((i for i, line in enumerate(lines) if "def upgrade()" in line), None)
    return "".join(lines[:line_num]) + f"{s}\n\n" + "".join(lines[line_num:]) if line_num else text


def create_migration_file(
    alembic_config: Config, sql_upgrade_str: str, sql_downgrade_str: str, message: str, preamble: str = ""
) -> None:
    if not (sql_upgrade_str or sql_downgrade_str):
        print("Nothing to do")  # noqa: T001, T201
        return

    print("Generating migration file.\n")  # noqa: T001, T201

    try:
        project_venv_location = " ".join(
            [
                location
                for location in alembic_config.get_main_option("version_locations", default="").split(" ")
                if orchestrator_module_location not in location
            ]
        )
        # Initial alembic migration generate that doesn't know about a branch 'data' and remove core down revision.
        script = ScriptDirectory.from_config(alembic_config)
        core_head = script.get_current_head()
        migration: Any = command.revision(
            alembic_config,
            message,
            branch_label="data",
            depends_on=core_head,
            version_path=project_venv_location,
        )

        remove_core_as_down_revision(migration)
    except CommandError as err:
        error_str = str(err)
        if ("Branch name 'data'" in error_str and "already used by revision" in error_str) or (
            "The script directory has multiple heads" in error_str
        ):
            try:
                migration = command.revision(alembic_config, message, head="data@head")
            except CommandError:
                if "Branch name 'data'" in error_str and "already used by revision" in error_str:
                    raise CommandError("Database not up to date with latest revision")
                raise CommandError("Database head 'data' already exists but no revision/migration file found")
        else:
            raise err

    with open(migration.path) as f:
        file_data = f.read()

    if preamble:
        file_data = _insert_preamble(file_data, preamble)

    new_file_data = file_data.replace("    pass", f"    conn = op.get_bind()\n{sql_upgrade_str}", 1)
    new_file_data = new_file_data.replace("    pass", f"    conn = op.get_bind()\n{sql_downgrade_str}", 1)
    with open(migration.path, "w") as f:
        f.write(new_file_data)

    print("Migration generated. Don't forget to create a database backup before migrating!")  # noqa: T001, T201

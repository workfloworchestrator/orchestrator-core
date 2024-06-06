import re
import sys
from difflib import context_diff
from filecmp import dircmp
from pathlib import Path

import pytest
import structlog
from more_itertools import one
from typer.testing import CliRunner

from orchestrator.cli.database import app as db_app
from orchestrator.cli.generate import app as generate_app

logger = structlog.get_logger()


def absolute_path(path: str) -> str:
    file = Path(__file__).resolve().parent / "data" / path
    return str(file)


def create_main():
    with open("main.py", "w") as fp:
        fp.write(
            "from orchestrator import OrchestratorCore\n"
            "from orchestrator.cli.main import app as core_cli\n"
            "from orchestrator.settings import AppSettings\n"
            "\n"
            "app = OrchestratorCore(base_settings=AppSettings())\n"
            'if __name__ == "__main__":\n'
            "    core_cli()\n"
        )


@pytest.fixture(scope="module")
def monkey_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture(scope="module")
def actual_folder(tmp_path_factory, monkey_module) -> Path:
    tmp_path = tmp_path_factory.mktemp("generate")
    monkey_module.chdir(tmp_path)
    sys.path.append(str(tmp_path))
    create_main()
    runner = CliRunner()
    runner.invoke(db_app, ["init"])
    for config_file in (absolute_path("product_config2.yaml"), absolute_path("product_config1.yaml")):
        for cmd in ("product-blocks", "product", "workflows", "unit-tests"):
            runner.invoke(generate_app, [cmd, "--config-file", config_file, "--no-dryrun", "--force"])
        runner.invoke(generate_app, ["migration", "--config-file", config_file])
    return tmp_path


@pytest.fixture(scope="module")
def expected_folder() -> Path:
    return Path(__file__).resolve().parent / "data" / "generate"


def test_missing_or_extra_files(expected_folder, actual_folder):
    def assert_equal_dirs(dcmp):
        left_only = ", ".join(dcmp.left_only)
        right_only = ", ".join(dcmp.right_only)
        relative_folder = Path(dcmp.right).relative_to(actual_folder)

        assert left_only == "", f"missing file(s) {left_only} from directory {relative_folder}"
        assert right_only == "", f"extra file(s) {right_only} in directory {relative_folder}"

        for sub_dcmp in dcmp.subdirs.values():
            assert_equal_dirs(sub_dcmp)

    assert_equal_dirs(dircmp(expected_folder, actual_folder, ignore=["versions", "__pycache__"]))  # skip migrations


def get_dynamic_migration_values(file):
    """Retrieve dynamic values from the given migration file."""
    line_prefixes = ["Revision ID:", "Revises:", "Create Date:", "revision =", "down_revision =", "depends_on ="]
    text = file.open().read()
    regex = r"^(?:(%s)(.*))$" % ("|".join(re.escape(v) for v in line_prefixes),)
    matches = re.findall(regex, text, flags=re.MULTILINE)
    return dict(matches)  # {"Revision ID:": "Revision ID: 59e1199aff7f", ...}


def update_dynamic_migration_values(file, replacements):
    """Update dynamic values in the migration file and return the content."""
    text = file.open().read()
    for prefix, replacement_line in replacements.items():
        regex_pattern = r"^(?:(%s)(.*))$" % (re.escape(prefix),)
        regex_replace = r"\1%s" % (replacement_line,)
        text = re.sub(regex_pattern, regex_replace, text, count=1, flags=re.MULTILINE)
    return text


def get_revision_ids(folder):
    """Find all alembic migrations and return a list of revision ids starting from the base.

    Note that this will only return the chain of revisions starting from the base revision.
    A warning will be logged in case of unconnected revisions because this is probably an error.
    """

    def showfile(file):
        return str(file.relative_to(folder))

    revision_chain = {}
    migration_files = list((folder / "migrations/versions/schema").glob("*.py"))
    rev_id_to_file = {}
    for migration_file in migration_files:
        _date, filename_rev_id, *_rest = migration_file.name.split("_")
        rev_ids = dict(re.findall(r'(.+) = "([0-9a-z]+)"', migration_file.open().read()))
        migration_rev_id = rev_ids["revision"]
        assert (
            filename_rev_id == migration_rev_id
        ), f"Migration file {showfile(migration_file)} has a different revision id in name and body"
        rev_id_to_file[migration_rev_id] = migration_file
        revision_chain[rev_ids.get("down_revision", "base")] = migration_rev_id

    def follow_rev(rev):
        if rev not in revision_chain:
            return
        yield revision_chain[rev]
        yield from follow_rev(revision_chain[rev])

    revision_history = list(follow_rev("base"))
    if len(migration_files) > len(revision_history):
        unconnected = [showfile(file) for rev_id, file in rev_id_to_file.items() if rev_id not in revision_history]
        logger.warning(
            "Not all migration files in this directory are connected to the chain of revisions",
            directory=folder,
            revision_chain=revision_history,
            unconnected=unconnected,
        )
    return revision_history


def get_expected_to_actual_migration_rev_ids(actual_folder, expected_folder):
    expected_revision_ids = get_revision_ids(expected_folder)
    actual_revision_ids = get_revision_ids(actual_folder)
    # If you're missing an expected migration, make sure it's down_revision correctly points to the previous one
    assert len(actual_revision_ids) == len(expected_revision_ids), (
        "Number of expected migration files does not match the number of actual migration files, "
        "check the logs above for hints"
    )
    return dict(zip(expected_revision_ids, actual_revision_ids))


def test_differences_in_generated_code(expected_folder, actual_folder):
    _expected_to_actual_rev_id = get_expected_to_actual_migration_rev_ids(actual_folder, expected_folder)

    def derive_actual_migration_file(expected_file):
        _expected_date, expected_rev_id, *rest = expected_file.name.split("_")
        actual_rev_id = _expected_to_actual_rev_id[expected_rev_id]
        return one((actual_folder / "migrations/versions/schema").glob(f"*_{actual_rev_id}_*.py"))

    for expected in expected_folder.rglob("*.py"):
        relative = expected.relative_to(expected_folder)
        actual = actual_folder / relative

        if not actual.exists():
            # Must be a migration file which is dynamic name (contains date and revision ID)
            actual = derive_actual_migration_file(expected)
            replacements = get_dynamic_migration_values(expected)
            tofile = f"actual {actual.relative_to(actual_folder)} (derived)"
            actual_lines = update_dynamic_migration_values(actual, replacements).splitlines(keepends=True)
        else:
            tofile = f"actual {relative}"
            actual_lines = actual.open().readlines()

        diff = context_diff(
            open(expected).readlines(), actual_lines, fromfile=f"expected {relative}", tofile=tofile, n=1, lineterm=""
        )

        formatted_diff = "\n".join(diff)
        if formatted_diff:
            print(f"\n{formatted_diff}")

        assert not formatted_diff, f"generated {relative} differs, see expected vs actual in the stdout output"

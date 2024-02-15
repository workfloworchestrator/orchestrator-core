import sys
from difflib import context_diff
from filecmp import dircmp
from pathlib import Path

import pytest
from typer.testing import CliRunner

from orchestrator.cli.database import app as db_app
from orchestrator.cli.generate import app as generate_app


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


def test_differences_in_generated_code(expected_folder, actual_folder):
    for expected in expected_folder.rglob("[!0-9]*.py"):  # skip migration versions for now (contain date and uniq id)
        relative = expected.relative_to(expected_folder)
        actual = actual_folder / relative
        diff = context_diff(
            open(expected).readlines(), open(actual).readlines(), fromfile="expected", tofile="actual", n=1, lineterm=""
        )

        assert list(diff) == [], f'generated {relative} differs (see "pytest -vv")'

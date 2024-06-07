import sys
from functools import partial

import pytest
from typer.testing import CliRunner

from orchestrator.cli.database import app as db_app
from test.unit_tests.cli.helpers import create_main


@pytest.fixture(scope="module")
def monkey_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture(scope="module")
def tmp_generate_path(tmp_path_factory):
    yield tmp_path_factory.mktemp("generate")


@pytest.fixture(scope="module")
def cli_invoke(tmp_generate_path, monkey_module):
    monkey_module.chdir(tmp_generate_path)
    sys.path.append(str(tmp_generate_path))
    create_main()

    runner = CliRunner()
    # Don't catch exceptions because this will cost you grey hair.
    invoke = partial(runner.invoke, catch_exceptions=False)
    invoke(db_app, ["init"])

    yield invoke

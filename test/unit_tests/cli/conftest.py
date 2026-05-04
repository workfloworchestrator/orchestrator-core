# Copyright 2019-2026 SURF, GÉANT.
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

import sys
from functools import partial

import pytest
from typer.testing import CliRunner

from orchestrator.core.cli.database import app as db_app
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

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

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "import_target",
    [
        "orchestrator.core.cli.main",
        "orchestrator.core.cli.database",
        "orchestrator.core.cli.scheduler",
    ],
)
def test_cli_module_import_speed(import_target: str) -> None:
    """CLI module imports should complete quickly without loading the full app stack."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {import_target}"],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_cli_does_not_import_app() -> None:
    """Importing CLI modules should not trigger loading orchestrator.core.app."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import orchestrator.core.cli.main; "
                "import sys; "
                "assert 'orchestrator.core.app' not in sys.modules, "
                "'cli.main should not import app.py'"
            ),
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr.decode()

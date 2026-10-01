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

from unittest.mock import ANY, MagicMock, call, patch

import pytest
from typer.testing import CliRunner

from orchestrator.core.cli.database import _index_search
from orchestrator.core.cli.database import app as db_app

COMMANDS = [
    pytest.param("upgrade", ["upgrade", "heads"], id="upgrade"),
    pytest.param("downgrade", ["downgrade", "base"], id="downgrade"),
]


@pytest.mark.parametrize(("alembic_command", "cli_args"), COMMANDS)
@pytest.mark.parametrize(
    ("flags", "expected_calls"),
    [
        pytest.param([], [call.migrate(ANY, ANY), call.index_all(force_index=False)], id="index_by_default"),
        pytest.param(["--force-index"], [call.migrate(ANY, ANY), call.index_all(force_index=True)], id="force_index"),
        pytest.param(["--no-index"], [call.migrate(ANY, ANY)], id="no_index"),
    ],
)
def test_migration_indexes_afterwards(alembic_command, cli_args, flags, expected_calls):
    manager = MagicMock()
    with (
        patch("orchestrator.core.cli.database.alembic_cfg"),
        patch(f"orchestrator.core.cli.database.command.{alembic_command}", manager.migrate),
        patch("orchestrator.core.cli.database._index_search", manager.index_all),
    ):
        result = CliRunner().invoke(db_app, [*cli_args, *flags], catch_exceptions=False)

    assert result.exit_code == 0
    assert manager.mock_calls == expected_calls


def test_index_search_runs_indexing():
    with (
        patch("orchestrator.core.cli.database._missing_search_tables", return_value=[]),
        patch("orchestrator.core.cli.database.run_indexing_for_all_entities") as mock_index,
    ):
        _index_search(force_index=True)

    mock_index.assert_called_once_with(force_index=True)


def test_index_search_skips_when_search_tables_missing():
    with (
        patch("orchestrator.core.cli.database._missing_search_tables", return_value=["ai_search_paths"]),
        patch("orchestrator.core.cli.database.run_indexing_for_all_entities") as mock_index,
    ):
        _index_search(force_index=False)

    mock_index.assert_not_called()

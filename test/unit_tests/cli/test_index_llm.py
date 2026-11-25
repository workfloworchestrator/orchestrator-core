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

"""Tests for the `index all` CLI command: option forwarding to run_indexing_for_all_entities."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from orchestrator.core.cli.search.index_llm import app

MODULE = "orchestrator.core.cli.search.index_llm"


def test_all_command_forwards_chunk_size_option():
    with patch(f"{MODULE}.run_indexing_for_all_entities") as mock_index:
        result = CliRunner().invoke(app, ["all", "--chunk-size", "500"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_index.assert_called_once_with(force_index=False, chunk_size=500)


def test_all_command_defaults_to_memory_bounded_chunk_size():
    with patch(f"{MODULE}.run_indexing_for_all_entities") as mock_index:
        result = CliRunner().invoke(app, ["all"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_index.assert_called_once_with(force_index=False, chunk_size=200)


@pytest.mark.parametrize("bad_size", [pytest.param("0", id="zero"), pytest.param("-1", id="negative")])
def test_all_command_rejects_nonpositive_chunk_size(bad_size):
    with patch(f"{MODULE}.run_indexing_for_all_entities") as mock_index:
        result = CliRunner().invoke(app, ["all", f"--chunk-size={bad_size}"], catch_exceptions=False)

    assert result.exit_code == 2
    assert "--chunk-size" in result.output
    mock_index.assert_not_called()

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

"""Tests for CLI input helpers: user input collection."""

from unittest import mock

from orchestrator.core.cli.helpers.input_helpers import get_user_input


@mock.patch("orchestrator.core.cli.helpers.input_helpers.input", return_value="  hello  ")
def test_get_user_input_strips(mock_input: mock.MagicMock) -> None:
    assert get_user_input("Enter: ") == "hello"


@mock.patch("orchestrator.core.cli.helpers.input_helpers.input", return_value="")
def test_get_user_input_default(mock_input: mock.MagicMock) -> None:
    assert get_user_input("Enter: ", default="default_val") == "default_val"


@mock.patch("orchestrator.core.cli.helpers.input_helpers.input", side_effect=["", "", "finally"])
def test_get_user_input_loops(mock_input: mock.MagicMock) -> None:
    assert get_user_input("Enter: ") == "finally"
    assert mock_input.call_count == 3

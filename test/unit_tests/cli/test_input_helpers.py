"""Tests for CLI input helpers: user input collection."""

from unittest import mock

from orchestrator.cli.helpers.input_helpers import get_user_input


@mock.patch("orchestrator.cli.helpers.input_helpers.input", return_value="  hello  ")
def test_get_user_input_strips(mock_input: mock.MagicMock) -> None:
    assert get_user_input("Enter: ") == "hello"


@mock.patch("orchestrator.cli.helpers.input_helpers.input", return_value="")
def test_get_user_input_default(mock_input: mock.MagicMock) -> None:
    assert get_user_input("Enter: ", default="default_val") == "default_val"


@mock.patch("orchestrator.cli.helpers.input_helpers.input", side_effect=["", "", "finally"])
def test_get_user_input_loops(mock_input: mock.MagicMock) -> None:
    assert get_user_input("Enter: ") == "finally"
    assert mock_input.call_count == 3

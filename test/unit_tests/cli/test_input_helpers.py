"""Tests for CLI input helpers: menu key enumeration, user prompts, and input collection."""

from unittest import mock

import pytest

from orchestrator.cli.helpers.input_helpers import _enumerate_menu_keys, _prompt_user_menu, get_user_input

_TWO_OPTIONS = [("Option A", "value_a"), ("Option B", "value_b")]
_THREE_OPTIONS = [("A", 1), ("B", 2), ("C", 3)]

# --- _enumerate_menu_keys ---


@pytest.mark.parametrize(
    "items,expected",
    [
        pytest.param(["a", "b", "c"], ["1", "2", "3"], id="list"),
        pytest.param([], [], id="empty"),
    ],
)
def test_enumerate_menu_keys(items: list, expected: list[str]) -> None:
    assert _enumerate_menu_keys(items) == expected


def test_enumerate_menu_keys_set() -> None:
    assert sorted(_enumerate_menu_keys({1, 2, 3})) == ["1", "2", "3"]


# --- get_user_input ---


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


# --- _prompt_user_menu ---


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="1")
def test_prompt_user_menu_valid(mock_gui: mock.MagicMock, mock_pf: mock.MagicMock) -> None:
    assert _prompt_user_menu(_TWO_OPTIONS) == "value_a"


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", side_effect=["x", "2"])
def test_prompt_user_menu_retry(mock_gui: mock.MagicMock, mock_pf: mock.MagicMock) -> None:
    assert _prompt_user_menu(_TWO_OPTIONS, repeat=True) == "value_b"
    assert mock_gui.call_count == 2


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="x")
def test_prompt_user_menu_no_repeat_returns_none(mock_gui: mock.MagicMock, mock_pf: mock.MagicMock) -> None:
    assert _prompt_user_menu([("Option A", "value_a")], repeat=False) is None


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="b")
def test_prompt_user_menu_custom_keys(mock_gui: mock.MagicMock, mock_pf: mock.MagicMock) -> None:
    assert _prompt_user_menu(_TWO_OPTIONS, keys=["a", "b"]) == "value_b"


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="3")
def test_prompt_user_menu_enumerated_keys(mock_gui: mock.MagicMock, mock_pf: mock.MagicMock) -> None:
    assert _prompt_user_menu(_THREE_OPTIONS) == 3

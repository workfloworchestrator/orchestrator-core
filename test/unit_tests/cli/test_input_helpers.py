from unittest import mock

import pytest

from orchestrator.cli.helpers.input_helpers import _enumerate_menu_keys, _prompt_user_menu, get_user_input

# ---------------------------------------------------------------------------
# _enumerate_menu_keys — pure function
# ---------------------------------------------------------------------------


def test_enumerate_menu_keys_list() -> None:
    assert _enumerate_menu_keys(["a", "b", "c"]) == ["1", "2", "3"]


def test_enumerate_menu_keys_set() -> None:
    result = _enumerate_menu_keys({1, 2, 3})
    assert sorted(result) == ["1", "2", "3"]


def test_enumerate_menu_keys_empty() -> None:
    assert _enumerate_menu_keys([]) == []


# ---------------------------------------------------------------------------
# get_user_input — mocked input()
# ---------------------------------------------------------------------------


@mock.patch("orchestrator.cli.helpers.input_helpers.input", return_value="  hello  ")
def test_get_user_input_returns_stripped_answer(mock_input: mock.MagicMock) -> None:
    result = get_user_input("Enter: ")
    assert result == "hello"
    mock_input.assert_called_once_with("Enter: ")


@mock.patch("orchestrator.cli.helpers.input_helpers.input", return_value="")
def test_get_user_input_returns_default_on_empty(mock_input: mock.MagicMock) -> None:
    result = get_user_input("Enter: ", default="default_val")
    assert result == "default_val"


@mock.patch("orchestrator.cli.helpers.input_helpers.input", return_value="")
def test_get_user_input_optional_returns_empty_default(mock_input: mock.MagicMock) -> None:
    result = get_user_input("Enter: ", optional=True)
    assert result == ""


@mock.patch("orchestrator.cli.helpers.input_helpers.input", side_effect=["", "", "finally"])
def test_get_user_input_loops_until_non_empty(mock_input: mock.MagicMock) -> None:
    result = get_user_input("Enter: ")
    assert result == "finally"
    assert mock_input.call_count == 3


# ---------------------------------------------------------------------------
# _prompt_user_menu — mocked get_user_input + print_fmt
# ---------------------------------------------------------------------------


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="1")
def test_prompt_user_menu_valid_selection(mock_get_user_input: mock.MagicMock, mock_print_fmt: mock.MagicMock) -> None:
    options = [("Option A", "value_a"), ("Option B", "value_b")]
    result = _prompt_user_menu(options)
    assert result == "value_a"


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", side_effect=["x", "2"])
def test_prompt_user_menu_invalid_then_valid_repeat_true(
    mock_get_user_input: mock.MagicMock, mock_print_fmt: mock.MagicMock
) -> None:
    options = [("Option A", "value_a"), ("Option B", "value_b")]
    result = _prompt_user_menu(options, repeat=True)
    assert result == "value_b"
    assert mock_get_user_input.call_count == 2


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="x")
def test_prompt_user_menu_invalid_no_repeat_returns_none(
    mock_get_user_input: mock.MagicMock, mock_print_fmt: mock.MagicMock
) -> None:
    options = [("Option A", "value_a")]
    result = _prompt_user_menu(options, repeat=False)
    assert result is None


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="b")
def test_prompt_user_menu_custom_keys(mock_get_user_input: mock.MagicMock, mock_print_fmt: mock.MagicMock) -> None:
    options = [("Option A", 10), ("Option B", 20)]
    result = _prompt_user_menu(options, keys=["a", "b"])
    assert result == 20


@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
@mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value="3")
def test_prompt_user_menu_default_keys_enumerated(
    mock_get_user_input: mock.MagicMock, mock_print_fmt: mock.MagicMock
) -> None:
    options = [("A", 1), ("B", 2), ("C", 3)]
    result = _prompt_user_menu(options)
    assert result == 3


@pytest.mark.parametrize("choice", ["1", "2"])
@mock.patch("orchestrator.cli.helpers.input_helpers.print_fmt")
def test_prompt_user_menu_prints_all_options(mock_print_fmt: mock.MagicMock, choice: str) -> None:
    options = [("Opt 1", "v1"), ("Opt 2", "v2")]
    with mock.patch("orchestrator.cli.helpers.input_helpers.get_user_input", return_value=choice):
        _prompt_user_menu(options)
    assert mock_print_fmt.call_count == len(options)

import builtins
from unittest import mock

import pytest

from orchestrator.cli.helpers.print_helpers import COLOR, noqa_print, print_fmt, str_fmt


@pytest.mark.parametrize(
    ("member", "expected_code"),
    [
        (COLOR.RESET, "\033[0m"),
        (COLOR.BOLD, "\033[1m"),
        (COLOR.DIM, "\033[2m"),
        (COLOR.ITALIC, "\033[3m"),
        (COLOR.UNDERLINE, "\033[4m"),
        (COLOR.BLACK, "\033[30m"),
        (COLOR.RED, "\033[31m"),
        (COLOR.GREEN, "\033[32m"),
        (COLOR.YELLOW, "\033[33m"),
        (COLOR.BLUE, "\033[34m"),
        (COLOR.MAGENTA, "\033[35m"),
        (COLOR.CYAN, "\033[36m"),
    ],
)
def test_color_enum_values(member: COLOR, expected_code: str) -> None:
    assert member == expected_code


def test_color_enum_is_str() -> None:
    for member in COLOR:
        assert isinstance(member, str)


def test_str_fmt_no_flags() -> None:
    result = str_fmt("hello")
    assert result == "hello" + COLOR.RESET


def test_str_fmt_single_flag() -> None:
    result = str_fmt("hello", flags=[COLOR.BOLD])
    assert result == COLOR.BOLD + "hello" + COLOR.RESET


def test_str_fmt_multiple_flags() -> None:
    result = str_fmt("hello", flags=[COLOR.BOLD, COLOR.RED])
    assert result == COLOR.BOLD + COLOR.RED + "hello" + COLOR.RESET


def test_str_fmt_empty_text() -> None:
    result = str_fmt("", flags=[COLOR.GREEN])
    assert result == COLOR.GREEN + COLOR.RESET


def test_print_fmt_calls_print_fn() -> None:
    mock_print = mock.MagicMock()
    print_fmt("hello", flags=[COLOR.CYAN], print_fn=mock_print)
    mock_print.assert_called_once_with(str_fmt("hello", flags=[COLOR.CYAN]))


def test_print_fmt_passes_kwargs() -> None:
    mock_print = mock.MagicMock()
    print_fmt("hello", print_fn=mock_print, end="", flush=True)
    mock_print.assert_called_once_with(str_fmt("hello"), end="", flush=True)


def test_print_fmt_default_uses_builtin_print() -> None:
    with mock.patch("orchestrator.cli.helpers.print_helpers.print") as mock_builtin_print:
        print_fmt("world", print_fn=mock_builtin_print)
        mock_builtin_print.assert_called_once_with(str_fmt("world"))


def test_noqa_print_delegates_to_print() -> None:
    with mock.patch.object(builtins, "print") as mock_builtin_print:
        noqa_print("test output", end="\n")
        mock_builtin_print.assert_called_once_with("test output", end="\n")

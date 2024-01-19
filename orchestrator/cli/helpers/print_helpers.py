from collections.abc import Callable, Iterable
from typing import Any

from orchestrator.types import strEnum


def _esc_str(i: int) -> str:
    return f"\033[{i}m"


class COLOR(strEnum):
    RESET = _esc_str(0)
    BOLD = _esc_str(1)
    DIM = _esc_str(2)
    ITALIC = _esc_str(3)
    UNDERLINE = _esc_str(4)

    BLACK = _esc_str(30)
    RED = _esc_str(31)
    GREEN = _esc_str(32)
    YELLOW = _esc_str(33)
    BLUE = _esc_str(34)
    MAGENTA = _esc_str(35)
    CYAN = _esc_str(36)


def str_fmt(text: str, *, flags: Iterable[COLOR] = ()) -> str:
    return "".join(f for f in flags) + text + COLOR.RESET


def print_fmt(text: str, *, flags: Iterable[COLOR] = (), print_fn: Callable = print, **kwargs: Any) -> None:
    print_fn(str_fmt(text, flags=flags), **kwargs)


def noqa_print(s: str, **kwargs: Any) -> None:
    print(s, **kwargs)  # noqa: T201

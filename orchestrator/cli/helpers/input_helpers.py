from typing import Iterable, List, Optional, Tuple, TypeVar

import structlog

from orchestrator.cli.helpers.print_helpers import print_fmt

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def get_user_input(text: str, default: str = "", optional: bool = False) -> str:
    while True:
        answer = input(text)
        if answer or default:
            return answer.strip() if answer else default
        if optional:
            return ""


def _enumerate_menu_keys(items: List) -> List[str]:
    return [str(i + 1) for i in range(len(items))]


def _prompt_user_menu(
    options: Iterable[Tuple[str, T]], keys: Optional[List[str]] = None, repeat: bool = True
) -> Optional[T]:
    options_list = list(options)
    keys = keys or _enumerate_menu_keys(options_list)
    done = False
    while not done:
        for k, txt_v in zip(keys, options_list):
            print_fmt(f"{k}) {txt_v[0]}")
        choice = get_user_input("? ")
        if choice not in keys:
            print_fmt("Invalid choice")
            done = not repeat
        else:
            return options_list[keys.index(choice)][1]
    return None

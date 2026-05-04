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

from collections.abc import Iterable
from typing import TypeVar

import structlog

from orchestrator.core.cli.helpers.print_helpers import print_fmt

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def get_user_input(text: str, default: str = "", optional: bool = False) -> str:
    while True:
        answer = input(text)
        if answer or default:
            return answer.strip() if answer else default
        if optional:
            return default


def _enumerate_menu_keys(items: list | set) -> list[str]:
    return [str(i + 1) for i in range(len(items))]


def _prompt_user_menu(options: Iterable[tuple[str, T]], keys: list[str] | None = None, repeat: bool = True) -> T | None:
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

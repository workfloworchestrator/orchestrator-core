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
from functools import singledispatch
from typing import Any

import pytest

from orchestrator.core.utils.singledispatch import single_dispatch_base


@singledispatch
def describe(value: Any) -> str:
    return single_dispatch_base(describe, value)


@describe.register
def _(value: int) -> str:
    return f"int {value}"


@describe.register
def _(value: str) -> str:
    return f"str {value}"


@singledispatch
def only_base(value: Any) -> str:
    return single_dispatch_base(only_base, value)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param(1, "int 1", id="int"),
        pytest.param("a", "str a", id="str"),
        pytest.param(True, "int True", id="bool-subclass-of-int"),
    ],
)
def test_registered_type_is_dispatched(value: Any, expected: str) -> None:
    assert describe(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(1.5, id="float"),
        pytest.param(None, id="none"),
        pytest.param([1], id="list"),
    ],
)
def test_unregistered_type_raises(value: Any) -> None:
    with pytest.raises(TypeError) as exc_info:
        describe(value)

    message = str(exc_info.value)
    assert message.startswith(f"`describe` called for unsupported model type {type(value)}.")
    assert "<class 'int'>" in message
    assert "<class 'str'>" in message
    assert "<class 'object'>" not in message


def test_only_base_registered_lists_no_supported_types() -> None:
    with pytest.raises(TypeError, match=r"Supported model types are: $"):
        only_base(1)

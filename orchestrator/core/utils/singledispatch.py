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
from collections.abc import Callable
from itertools import filterfalse
from typing import Any, NoReturn


def single_dispatch_base(func: Callable, value: Any) -> NoReturn:
    """Raise a TypeError for a `@singledispatch` generic function called with an unregistered type.

    Use this as the body of the generic (base) implementation of a `@singledispatch` function.

    Args:
        func: The `@singledispatch` generic function.
        value: The value the generic function was called with.

    Raises:
        TypeError: always, listing the model types that do have a registered implementation.
    """
    registry = func.registry  # type: ignore[attr-defined]

    supported_models = ", ".join(map(str, filterfalse(lambda t: t is object, registry.keys())))
    raise TypeError(
        f"`{func.__name__}` called for unsupported model type {type(value)}. "
        f"Supported model types are: {supported_models}"
    )

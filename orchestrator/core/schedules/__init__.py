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
import warnings
from typing import Any

__all__ = ["ALL_SCHEDULERS"]
_ALL_SCHEDULERS: list[Any] = []


def __getattr__(name: str) -> list[Any]:
    """Return deprecated module attributes."""
    if name != "ALL_SCHEDULERS":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    warnings.warn(
        "ALL_SCHEDULERS is deprecated and will be removed in 6.0.0. "
        "Scheduling tasks can now be handled entirely through the API. "
        "For more details, please consult https://workfloworchestrator.org/orchestrator-core/guides/upgrading/4.7/",
        DeprecationWarning,
        stacklevel=2,
    )
    return _ALL_SCHEDULERS

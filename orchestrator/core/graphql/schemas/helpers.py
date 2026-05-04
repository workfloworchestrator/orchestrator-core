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

from typing import Any, TypeVar, cast

T = TypeVar("T")


def get_original_model(model: Any, klass: T) -> T:
    """Get original type in a typesafe way."""
    original_model = getattr(model, "_original_model", None)

    if original_model:
        return cast(T, original_model)
    raise ValueError(f"Cant get original model for type {klass}")

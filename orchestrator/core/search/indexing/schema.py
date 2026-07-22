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

"""Shared helpers for traversing Pydantic model field annotations."""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel


def iter_model_field_annotations(model_type: type[BaseModel]) -> Iterable[tuple[str, Any]]:
    """Yield declared and computed field names with their annotations."""
    fields = model_type.model_fields.copy()
    fields.update(getattr(model_type, "__pydantic_computed_fields__", {}))
    for name, field in fields.items():
        yield name, field.annotation if hasattr(field, "annotation") else field.return_type

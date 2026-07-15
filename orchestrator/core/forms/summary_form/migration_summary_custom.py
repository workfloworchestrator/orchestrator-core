# Copyright 2026 SURF.
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

from functools import partial
from types import new_class
from typing import Annotated, Any

from pydantic import Field

from pydantic_forms.types import SummaryData
from pydantic_forms.validators.components.migration_summary import _MigrationSummary

MigrationSummary = Annotated[_MigrationSummary, Field(frozen=True, default=None, validate_default=False)]


def create_json_extra_schema(data: SummaryData, schema: dict[str, Any]) -> None:
    schema.update({"format": "summary", "type": "string", "uniforms": {"data": data}})
    # TODO: check if Frontend renders MigrationSummary ok
    # Error: no "allOf" anymore in pydantic JSON scheme
    schema.pop("allOf", None)  # This is needed, because otherwise frontend is unable to render this schema


def migration_summary_custom(data: SummaryData) -> type[MigrationSummary]:
    namespace = {"data": data}
    klass: type[MigrationSummary] = new_class(
        "MigrationSummaryValue", (_MigrationSummary,), {}, lambda ns: ns.update(namespace)
    )

    json_schema_extra = partial(create_json_extra_schema, data)

    return Annotated[
        klass, Field(frozen=True, default=None, validate_default=False, json_schema_extra=json_schema_extra)
    ]  # type: ignore

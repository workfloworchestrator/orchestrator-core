# Copyright 2019-2025 SURF, GÉANT.
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

from typing import Literal

from pydantic import BaseModel, ConfigDict

from orchestrator.search.core.types import FieldType, FilterOp, UIType


class ValueSchema(BaseModel):
    """Schema describing the expected value type for a filter operator."""

    kind: UIType | Literal["none", "object"] = UIType.STRING
    fields: dict[str, "ValueSchema"] | None = None

    model_config = ConfigDict(extra="forbid")


class TypeDefinition(BaseModel):
    """Definition of available operators and their value schemas for a field type."""

    operators: list[FilterOp]
    value_schema: dict[FilterOp, ValueSchema]

    model_config = ConfigDict(use_enum_values=True)


def operators_for(ft: FieldType) -> list[FilterOp]:
    """Return the list of valid operators for a given FieldType."""
    return list(value_schema_for(ft).keys())


def component_operators() -> dict[FilterOp, ValueSchema]:
    """Return operators available for path components."""
    return {
        FilterOp.HAS_COMPONENT: ValueSchema(kind=UIType.COMPONENT),
        FilterOp.NOT_HAS_COMPONENT: ValueSchema(kind=UIType.COMPONENT),
    }


def value_schema_for(ft: FieldType) -> dict[FilterOp, ValueSchema]:
    """Return the value schema map for a given FieldType."""
    if ft in (FieldType.INTEGER, FieldType.FLOAT):
        return {
            FilterOp.EQ: ValueSchema(kind=UIType.NUMBER),
            FilterOp.NEQ: ValueSchema(kind=UIType.NUMBER),
            FilterOp.LT: ValueSchema(kind=UIType.NUMBER),
            FilterOp.LTE: ValueSchema(kind=UIType.NUMBER),
            FilterOp.GT: ValueSchema(kind=UIType.NUMBER),
            FilterOp.GTE: ValueSchema(kind=UIType.NUMBER),
            FilterOp.BETWEEN: ValueSchema(
                kind="object",
                fields={
                    "start": ValueSchema(kind=UIType.NUMBER),
                    "end": ValueSchema(kind=UIType.NUMBER),
                },
            ),
        }

    if ft == FieldType.BOOLEAN:
        return {
            FilterOp.EQ: ValueSchema(kind=UIType.BOOLEAN),
            FilterOp.NEQ: ValueSchema(kind=UIType.BOOLEAN),
        }

    if ft == FieldType.DATETIME:
        return {
            FilterOp.EQ: ValueSchema(kind=UIType.DATETIME),
            FilterOp.NEQ: ValueSchema(kind=UIType.DATETIME),
            FilterOp.LT: ValueSchema(kind=UIType.DATETIME),
            FilterOp.LTE: ValueSchema(kind=UIType.DATETIME),
            FilterOp.GT: ValueSchema(kind=UIType.DATETIME),
            FilterOp.GTE: ValueSchema(kind=UIType.DATETIME),
            FilterOp.BETWEEN: ValueSchema(
                kind="object",
                fields={
                    "start": ValueSchema(kind=UIType.DATETIME),
                    "end": ValueSchema(kind=UIType.DATETIME),
                },
            ),
        }

    return {
        FilterOp.EQ: ValueSchema(kind=UIType.STRING),
        FilterOp.NEQ: ValueSchema(kind=UIType.STRING),
        FilterOp.LIKE: ValueSchema(kind=UIType.STRING),
    }


def generate_definitions() -> dict[UIType, TypeDefinition]:
    """Generate the full definitions dictionary for all UI types."""
    definitions: dict[UIType, TypeDefinition] = {}

    for ui_type in UIType:
        if ui_type == UIType.COMPONENT:
            # Special case for component filtering
            comp_ops = component_operators()
            definitions[ui_type] = TypeDefinition(
                operators=list(comp_ops.keys()),
                value_schema=comp_ops,
            )
        else:
            # Regular field types
            if ui_type == UIType.NUMBER:
                rep_ft = FieldType.INTEGER
            elif ui_type == UIType.DATETIME:
                rep_ft = FieldType.DATETIME
            elif ui_type == UIType.BOOLEAN:
                rep_ft = FieldType.BOOLEAN
            else:
                rep_ft = FieldType.STRING

            definitions[ui_type] = TypeDefinition(
                operators=operators_for(rep_ft),
                value_schema=value_schema_for(rep_ft),
            )
    return definitions

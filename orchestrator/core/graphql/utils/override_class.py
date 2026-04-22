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

from strawberry.types.field import StrawberryField


def override_class(strawberry_class: type, fields: list[StrawberryField]) -> type:
    """Override fields or add fields to a existing strawberry class.

    Usefull for overriding orchestrator core strawberry classes.

    Parameters:
        - strawberry_class: The strawberry class which you want to change fields.
        - fields: a dict with strawberry fields to override or add to the strawberry class.

    returns the strawberry class with changed fields.
    """

    if not fields:
        return strawberry_class

    if (definition := getattr(strawberry_class, "__strawberry_definition__", None)) is None:
        raise TypeError("Cannot override fields for a class without __strawberry_definition__")

    fields_map = {field.name: field for field in fields}

    def override_fn(field: StrawberryField) -> StrawberryField:
        if custom_field := fields_map.get(field.name):
            field.base_resolver = custom_field.base_resolver  # type: ignore[assignment]
            return field
        return field

    default_class_field_names = [field.name for field in definition.fields]

    new_field_list = [override_fn(field) for field in definition.fields]
    new_field_list.extend([field for field in fields if field.name not in default_class_field_names])

    definition.fields = new_field_list
    return strawberry_class

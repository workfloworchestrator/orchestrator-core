# Copyright 2019-2020 SURF.
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


def get_non_standard_fields(fields: list[dict]) -> str:
    return ", ".join(type for field in fields if (type := field["type"]) not in ["enum", "int", "bool", "str"])


def is_enum(field: dict) -> bool:
    return field["type"] == "enum"


def is_enum_of_type(field: dict, enum_type: str) -> bool:
    return is_enum(field) and field["enum_type"] == enum_type


def is_str_enum(field: dict) -> bool:
    return is_enum_of_type(field, "str")


def is_int_enum(field: dict) -> bool:
    return is_enum_of_type(field, "int")


def has_default(field: dict) -> bool:
    return "default" in field


def convert_enum(field: dict) -> dict:
    if is_enum(field):
        enum_type = field["name"].title()
        if has_default(field):
            if is_int_enum(field):
                field["default"] = enum_type + "._" + field["default"]
            elif is_str_enum(field):
                field["default"] = enum_type + "." + field["default"]
        return field | {"type": enum_type}
    return field


def convert_str_enum(field: dict) -> dict:
    return field | {"type": (enum_type := field["name"].title())} | {"default": enum_type + "." + field["default"]}


def get_str_enums(fields: list[dict]) -> list[dict]:
    return [convert_str_enum(field) for field in fields if is_str_enum(field)]


def get_int_enums(fields: list[dict]) -> list[dict]:
    return [convert_enum(field) for field in fields if is_int_enum(field)]


def replace_enum_type(fields: list[dict]) -> list[dict]:
    return [convert_enum(field) for field in fields]


# def replace_int_default(field: dict) -> dict:
#     return field | {"default": field["type"] + "._" + field["default"]}
#
#
# def replace_str_default(field: dict) -> dict:
#     return field | {"default": field["type"] + '."' + field["default"] + '"'}
#
#
# def replace_default(field: dict) -> dict:
#     return replace_int_default(field) if is_int_enum(field) else replace_str_default(field)


# def replace_enum_default(fields: list[dict]) -> list[dict]:
#     return [replace_default(field) if is_enum(field) and "default" in field else field for field in fields]

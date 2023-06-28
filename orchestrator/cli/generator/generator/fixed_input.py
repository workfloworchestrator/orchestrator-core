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


def get_non_standard_fixed_inputs(fixed_inputs: list[dict]) -> str:
    return ", ".join(type for fi in fixed_inputs if (type := fi["type"]) not in ["enum", "int", "bool", "str"])


def is_enum(fixed_input: dict) -> bool:
    return fixed_input["type"] == "enum"


def is_enum_of_type(fixed_input: dict, enum_type: str) -> bool:
    return is_enum(fixed_input) and fixed_input["enum_type"] == enum_type


def is_str_enum(fixed_input: dict) -> bool:
    return is_enum_of_type(fixed_input, "str")


def is_int_enum(fixed_input: dict) -> bool:
    return is_enum_of_type(fixed_input, "int")


def convert_enum(fixed_input: dict) -> dict:
    if is_enum(fixed_input):
        return fixed_input | {"type": fixed_input["name"].title()}
    return fixed_input


def get_str_enum_fixed_inputs(fixed_inputs: list[dict]) -> list[dict]:
    return [convert_enum(fi) for fi in fixed_inputs if is_str_enum(fi)]


def get_int_enum_fixed_inputs(fixed_inputs: list[dict]) -> list[dict]:
    return [convert_enum(fi) for fi in fixed_inputs if is_int_enum(fi)]


def replace_enum_fixed_inputs(fixed_inputs: list[dict]) -> list[dict]:
    return [convert_enum(fi) for fi in fixed_inputs]

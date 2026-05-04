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

from orchestrator.core.cli.generator.generator.enums import convert_int_enum, convert_str_enum


def test_convert_str_enum():
    field = {
        "default": "tagged",
        "enum_type": "str",
        "name": "port_mode",
        "type": "enum",
        "values": ["untagged", "tagged", "link_member"],
    }
    converted_field = convert_str_enum(field)
    assert converted_field["type"] == "PortMode"
    assert converted_field["default"] == "PortMode.tagged"


def test_convert_int_enum():
    field = {
        "default": 40000,
        "enum_type": "int",
        "name": "speed",
        "type": "enum",
        "values": [1000, 10000, 40000, 100000],
    }
    converted_field = convert_int_enum(field)
    assert converted_field["type"] == "Speed"
    assert converted_field["default"] == "Speed._40000"

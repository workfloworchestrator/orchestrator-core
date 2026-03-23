# Copyright 2022-2023 SURF.
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
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

import pytest

from orchestrator.utils.helpers import (
    camel_to_snake,
    create_filter_string,
    get_target_values,
    is_ipaddress_type,
    map_class,
    map_to_type,
    map_value,
    snake_to_camel,
    to_camel,
    to_snake,
)


class TestCreateFilterString:
    def test_returns_joined_string(self):
        assert create_filter_string(["a", "b", "c"]) == "a,b,c"

    def test_returns_empty_string_for_none(self):
        assert create_filter_string(None) == ""

    def test_returns_empty_string_for_empty_list(self):
        assert create_filter_string([]) == ""

    def test_single_element(self):
        assert create_filter_string(["only"]) == "only"


class TestToCamel:
    @pytest.mark.parametrize(
        "snake, expected",
        [
            ("hello_world", "helloWorld"),
            ("foo_bar_baz", "fooBarBaz"),
            ("single", "single"),
            ("already_camel_case", "alreadyCamelCase"),
        ],
        ids=["two_parts", "three_parts", "no_underscore", "multiple_underscores"],
    )
    def test_converts_snake_to_lower_camel(self, snake, expected):
        assert to_camel(snake) == expected


class TestToSnake:
    @pytest.mark.parametrize(
        "camel, expected",
        [
            ("helloWorld", "hello_world"),
            ("FooBarBaz", "foo_bar_baz"),
            ("already_snake", "already_snake"),
            ("XMLParser", "x_m_l_parser"),
        ],
        ids=["lower_camel", "upper_camel", "already_snake", "all_caps_prefix"],
    )
    def test_converts_camel_to_snake(self, camel, expected):
        assert to_snake(camel) == expected


class TestSnakeToCamel:
    @pytest.mark.parametrize(
        "snake, expected",
        [
            ("hello_world", "HelloWorld"),
            ("foo_bar_baz", "FooBarBaz"),
            ("single", "Single"),
        ],
        ids=["two_parts", "three_parts", "single_word"],
    )
    def test_converts_to_upper_camel(self, snake, expected):
        assert snake_to_camel(snake) == expected


class TestCamelToSnake:
    @pytest.mark.parametrize(
        "camel, expected",
        [
            ("HelloWorld", "hello_world"),
            ("FooBarBaz", "foo_bar_baz"),
            ("XMLParser", "xml_parser"),
            ("getHTTPResponse", "get_http_response"),
            ("alreadySnake", "already_snake"),
            ("simple", "simple"),
        ],
        ids=["upper_camel", "three_parts", "leading_acronym", "mid_acronym", "lower_camel", "single_word"],
    )
    def test_converts_camel_to_snake(self, camel, expected):
        assert camel_to_snake(camel) == expected


class TestIsIpaddressType:
    @pytest.mark.parametrize(
        "value",
        [
            IPv4Address("192.168.0.1"),
            IPv6Address("::1"),
            IPv4Network("10.0.0.0/8"),
            IPv6Network("2001:db8::/32"),
        ],
        ids=["ipv4_address", "ipv6_address", "ipv4_network", "ipv6_network"],
    )
    def test_returns_true_for_ip_types(self, value):
        assert is_ipaddress_type(value) is True

    @pytest.mark.parametrize(
        "value",
        ["192.168.0.1", 12345, None, object()],
        ids=["string", "int", "none", "object"],
    )
    def test_returns_false_for_non_ip_types(self, value):
        assert is_ipaddress_type(value) is False


class TestGetTargetValues:
    def test_returns_only_annotated_keys(self):
        class Foo:
            x: int
            y: str

        source = {"x": 1, "y": "hello", "z": 99}
        result = get_target_values(source, Foo)
        assert result == {"x": 1, "y": "hello"}

    def test_returns_empty_dict_when_no_match(self):
        class Foo:
            x: int

        source = {"a": 1, "b": 2}
        result = get_target_values(source, Foo)
        assert result == {}

    def test_returns_empty_dict_for_empty_source(self):
        class Foo:
            x: int

        result = get_target_values({}, Foo)
        assert result == {}


class TestMapClass:
    def test_maps_flat_class(self):
        class Foo:
            x: int

        result = map_class({}, {"x": 1, "extra": 2}, Foo)
        assert result == {"x": 1}

    def test_includes_base_class_annotations(self):
        class Base:
            x: int

        class Child(Base):
            y: str

        source = {"x": 1, "y": "hello", "z": 99}
        result = map_class({}, source, Child)
        assert result == {"x": 1, "y": "hello"}

    def test_child_overrides_base_value(self):
        class Base:
            x: int

        class Child(Base):
            x: int  # re-declared

        result = map_class({}, {"x": 42}, Child)
        assert result == {"x": 42}

    def test_skips_object_base(self):
        class Foo:
            x: int

        # object is in Foo.__bases__ but must be skipped
        result = map_class({}, {"x": 1}, Foo)
        assert result == {"x": 1}


class TestMapToType:
    def test_constructs_instance_from_source(self):
        class Foo:
            x: int
            y: str

            def __init__(self, x: int, y: str) -> None:
                self.x = x
                self.y = y

        result = map_to_type(Foo, {"x": 1, "y": "hi"})
        assert result.x == 1
        assert result.y == "hi"

    def test_warns_on_unmapped_fields(self, caplog):
        import logging

        class Foo:
            x: int

            def __init__(self, x: int) -> None:
                self.x = x

        with caplog.at_level(logging.WARNING, logger="orchestrator.utils.helpers"):
            map_to_type(Foo, {"x": 1, "unknown": 99})

    def test_no_warning_when_warn_if_missing_false(self, caplog):
        import logging

        class Foo:
            x: int

            def __init__(self, x: int) -> None:
                self.x = x

        with caplog.at_level(logging.WARNING, logger="orchestrator.utils.helpers"):
            result = map_to_type(Foo, {"x": 1, "unknown": 99}, warn_if_missing=False)
        assert result.x == 1


class TestMapValue:
    def test_applies_mapping_function_to_scalar(self):
        mapping = {"x": lambda v: v * 2}
        assert map_value(mapping, "x", 5) == ("x", 10)

    def test_applies_mapping_function_to_dict(self):
        mapping = {"x": lambda a, b: a + b}
        assert map_value(mapping, "x", {"a": 1, "b": 2}) == ("x", 3)

    def test_returns_none_when_value_is_none(self):
        mapping = {"x": lambda v: v * 2}
        assert map_value(mapping, "x", None) == ("x", None)

    def test_returns_key_value_unchanged_when_no_mapping(self):
        assert map_value({}, "x", 42) == ("x", 42)

    def test_function_can_return_custom_tuple(self):
        mapping = {"x": lambda v: ("renamed", v + 1)}
        assert map_value(mapping, "x", 5) == ("renamed", 6)

    def test_dict_function_can_return_custom_tuple(self):
        mapping = {"x": lambda a: ("renamed", a)}
        assert map_value(mapping, "x", {"a": 7}) == ("renamed", 7)

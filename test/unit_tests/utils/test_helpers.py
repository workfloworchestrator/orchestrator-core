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

"""Tests for string conversion helpers, IP type detection, annotation-based mapping, and value transformation."""

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

# --- create_filter_string ---


@pytest.mark.parametrize(
    "values,expected",
    [
        pytest.param(["a", "b", "c"], "a,b,c", id="joined"),
        pytest.param(None, "", id="none"),
        pytest.param([], "", id="empty"),
        pytest.param(["only"], "only", id="single"),
    ],
)
def test_create_filter_string(values: list[str] | None, expected: str) -> None:
    assert create_filter_string(values) == expected


# --- to_camel ---


@pytest.mark.parametrize(
    "snake,expected",
    [
        pytest.param("hello_world", "helloWorld", id="two-parts"),
        pytest.param("foo_bar_baz", "fooBarBaz", id="three-parts"),
        pytest.param("single", "single", id="no-underscore"),
    ],
)
def test_to_camel(snake: str, expected: str) -> None:
    assert to_camel(snake) == expected


# --- to_snake ---


@pytest.mark.parametrize(
    "camel,expected",
    [
        pytest.param("helloWorld", "hello_world", id="lower-camel"),
        pytest.param("FooBarBaz", "foo_bar_baz", id="upper-camel"),
        pytest.param("already_snake", "already_snake", id="already-snake"),
        pytest.param("XMLParser", "x_m_l_parser", id="all-caps-prefix"),
    ],
)
def test_to_snake(camel: str, expected: str) -> None:
    assert to_snake(camel) == expected


# --- snake_to_camel ---


@pytest.mark.parametrize(
    "snake,expected",
    [
        pytest.param("hello_world", "HelloWorld", id="two-parts"),
        pytest.param("single", "Single", id="single-word"),
    ],
)
def test_snake_to_camel(snake: str, expected: str) -> None:
    assert snake_to_camel(snake) == expected


# --- camel_to_snake ---


@pytest.mark.parametrize(
    "camel,expected",
    [
        pytest.param("HelloWorld", "hello_world", id="upper-camel"),
        pytest.param("XMLParser", "xml_parser", id="leading-acronym"),
        pytest.param("getHTTPResponse", "get_http_response", id="mid-acronym"),
        pytest.param("simple", "simple", id="single-word"),
    ],
)
def test_camel_to_snake(camel: str, expected: str) -> None:
    assert camel_to_snake(camel) == expected


# --- is_ipaddress_type ---


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param(IPv4Address("192.168.0.1"), True, id="ipv4-addr"),
        pytest.param(IPv6Address("::1"), True, id="ipv6-addr"),
        pytest.param(IPv4Network("10.0.0.0/8"), True, id="ipv4-net"),
        pytest.param(IPv6Network("2001:db8::/32"), True, id="ipv6-net"),
        pytest.param("192.168.0.1", False, id="string"),
        pytest.param(12345, False, id="int"),
        pytest.param(None, False, id="none"),
    ],
)
def test_is_ipaddress_type(value: object, expected: bool) -> None:
    assert is_ipaddress_type(value) is expected


# --- get_target_values ---


def test_get_target_values_filters_by_annotations() -> None:
    class Foo:
        x: int
        y: str

    assert get_target_values({"x": 1, "y": "hi", "z": 99}, Foo) == {"x": 1, "y": "hi"}


def test_get_target_values_empty_source() -> None:
    class Foo:
        x: int

    assert get_target_values({}, Foo) == {}


# --- map_class ---


def test_map_class_includes_base_annotations() -> None:
    class Base:
        x: int

    class Child(Base):
        y: str

    assert map_class({}, {"x": 1, "y": "hi", "z": 99}, Child) == {"x": 1, "y": "hi"}


# --- map_to_type ---


def test_map_to_type_constructs_instance() -> None:
    class Foo:
        x: int

        def __init__(self, x: int) -> None:
            self.x = x

    assert map_to_type(Foo, {"x": 1}).x == 1


def test_map_to_type_no_warning_when_disabled(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    class Foo:
        x: int

        def __init__(self, x: int) -> None:
            self.x = x

    with caplog.at_level(logging.WARNING, logger="orchestrator.utils.helpers"):
        map_to_type(Foo, {"x": 1, "unknown": 99}, warn_if_missing=False)
    assert caplog.records == []


# --- map_value ---


@pytest.mark.parametrize(
    "mapping,key,value,expected",
    [
        pytest.param({"x": lambda v: v * 2}, "x", 5, ("x", 10), id="scalar-transform"),
        pytest.param({"x": lambda a, b: a + b}, "x", {"a": 1, "b": 2}, ("x", 3), id="dict-unpack"),
        pytest.param({"x": lambda v: v * 2}, "x", None, ("x", None), id="none-passthrough"),
        pytest.param({}, "x", 42, ("x", 42), id="no-mapping"),
    ],
)
def test_map_value(mapping: dict, key: str, value: object, expected: tuple) -> None:
    assert map_value(mapping, key, value) == expected

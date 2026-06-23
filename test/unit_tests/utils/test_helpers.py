# Copyright 2022-2026 SURF, GÉANT.
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

"""Tests for string conversion helpers and IP type detection."""

from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

import pytest

from orchestrator.core.utils.helpers import (
    camel_to_snake,
    is_ipaddress_type,
    snake_to_camel,
    to_camel,
)

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

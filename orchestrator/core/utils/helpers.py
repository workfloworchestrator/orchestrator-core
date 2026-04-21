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
import re
from collections.abc import Callable
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Any, TypeVar

import structlog

T = TypeVar("T")


logger = structlog.get_logger(__name__)


def create_filter_string(input: list[str] | None) -> str:
    return ",".join(input) if input else ""


# Note: someday we might want to use Pydantic for this, but right now Pydantic support in Strawberry is experimental


def get_target_values(source: dict, klass: Any) -> dict:
    target = set(klass.__annotations__.keys())

    return {k: v for k, v in source.items() if k in target}


def map_class(target: dict, source: dict, klass: Any) -> dict:
    base_classes = (base for base in klass.__bases__ if base is not object)
    for base in base_classes:
        map_class(target, source, base)

    target |= get_target_values(source, klass)

    return target


def map_to_type(cls: type, source: dict, warn_if_missing: bool = True) -> T:  # type: ignore
    """Map to a type, assuming fields that need to be mapped are mapped in advance.

    class Foo:
        x: int

    class Bar:
        foos: list[Foo]

    # map the foos field to its own class

    source["foos"] = [map_to_type(Foo, foo) for foo in source["foos"]
    bar = map_to_type(Bar, source)
    """
    values = map_class({}, source, cls)

    if warn_if_missing:
        warn_if_unmapped_fields(source, values)

    return cls(**values)


def warn_if_unmapped_fields(source: dict, used: dict) -> None:
    if unmapped_fields := [key for key in source.keys() if key not in used.keys()]:
        keys = ",".join(unmapped_fields)
        logger.warning("Found unused keys", keys=keys)


def map_value(mapping: dict[str, Callable], k: str, v: Any) -> tuple[Any, ...]:
    if f := mapping.get(k):
        if v is None:
            return k, None
        if isinstance(v, dict):
            return result if type(result := f(**v)) is tuple else (k, result)
        return result if type(result := f(v)) is tuple else (k, result)
    return k, v


def to_camel(s: str) -> str:
    first, *rest = s.split("_")
    return first + "".join(word.title() for word in rest)


def to_snake(s: str) -> str:
    return "".join(["_" + c.lower() if c.isupper() else c for c in s]).lstrip("_")


def is_ipaddress_type(v: Any) -> bool:
    return isinstance(v, (IPv4Address, IPv6Address, IPv4Network, IPv6Network))


def snake_to_camel(s: str) -> str:
    return "".join(x.title() for x in s.split("_"))


def camel_to_snake(s: str) -> str:
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", s)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()

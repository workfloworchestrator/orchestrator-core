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
import re
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Any


def to_camel(s: str) -> str:
    first, *rest = s.split("_")
    return first + "".join(word.title() for word in rest)


def is_ipaddress_type(v: Any) -> bool:
    return isinstance(v, (IPv4Address, IPv6Address, IPv4Network, IPv6Network))


def snake_to_camel(s: str) -> str:
    return "".join(x.title() for x in s.split("_"))


def camel_to_snake(s: str) -> str:
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", s)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()

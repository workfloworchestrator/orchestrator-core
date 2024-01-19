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

from collections.abc import Awaitable, Callable
from ipaddress import IPv4Address, IPv4Interface, IPv6Address, IPv6Interface

# Map some Orchestrator types to scalars
from typing import Any, NewType

import strawberry
from graphql import GraphQLError
from starlette.requests import Request
from strawberry.custom_scalar import ScalarDefinition, ScalarWrapper
from strawberry.scalars import JSON
from strawberry.types import Info
from strawberry.types.info import RootValueType

from nwastdlib.vlans import VlanRanges
from oauth2_lib.fastapi import OIDCUserModel
from oauth2_lib.strawberry import OauthContext
from orchestrator.db.filters import Filter
from orchestrator.db.sorting import Sort, SortOrder


def serialize_to_string(value: Any) -> str:
    return str(value)


def serialize_vlan(vlan: VlanRanges) -> list[tuple[int, int]]:
    return vlan.to_list_of_tuples()


class OrchestratorContext(OauthContext):
    def __init__(
        self,
        get_current_user: Callable[[Request], Awaitable[OIDCUserModel]],
        get_opa_decision: Callable[[str, OIDCUserModel], Awaitable[bool | None]],
    ):
        self.errors: list[GraphQLError] = []
        super().__init__(get_current_user, get_opa_decision)


OrchestratorInfo = Info[OrchestratorContext, RootValueType]


@strawberry.experimental.pydantic.input(model=Sort)
class GraphqlSort:
    field: str = strawberry.field(description="Field to sort on")
    order: SortOrder = strawberry.field(default=SortOrder.ASC, description="Sort order (ASC or DESC")


@strawberry.experimental.pydantic.input(model=Filter)
class GraphqlFilter:
    field: str = strawberry.field(description="Field to filter on")
    value: str = strawberry.field(description="Value to sort the field on")


VlanRangesType = strawberry.scalar(
    NewType("VlanRangesType", str),
    description="Represent the Orchestrator VlanRanges data type",
    serialize=serialize_vlan,
    parse_value=lambda v: v,
)

IPv4AddressType = strawberry.scalar(
    NewType("IPv4AddressType", str),
    description="Represent the Orchestrator IPv4Address data type",
    serialize=serialize_to_string,
    parse_value=lambda v: v,
)

IPv6AddressType = strawberry.scalar(
    NewType("IPv6AddressType", str),
    description="Represent the Orchestrator IPv6Address data type",
    serialize=serialize_to_string,
    parse_value=lambda v: v,
)

IPv4InterfaceType = strawberry.scalar(
    NewType("IPv4InterfaceType", str),
    description="Represent the Orchestrator IPv4Interface data type",
    serialize=serialize_to_string,
    parse_value=lambda v: v,
)

IPv6InterfaceType = strawberry.scalar(
    NewType("IPv6InterfaceType", str),
    description="Represent the Orchestrator IPv6Interface data type",
    serialize=serialize_to_string,
    parse_value=lambda v: v,
)

IntType = strawberry.scalar(
    NewType("Int", int),
    description="An arbitrary precision integer",
    serialize=lambda v: v,
    parse_value=lambda v: v,
)

SCALAR_OVERRIDES: dict[object, Any | ScalarWrapper | ScalarDefinition] = {
    dict: JSON,
    VlanRanges: VlanRangesType,
    IPv4Address: IPv4AddressType,
    IPv6Address: IPv6AddressType,
    IPv4Interface: IPv4InterfaceType,
    IPv6Interface: IPv6InterfaceType,
    int: IntType,
}

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

from ipaddress import IPv4Address, IPv4Interface, IPv6Address, IPv6Interface

# Map some Orchestrator types to scalars
from typing import Any, Callable, List, NewType, Tuple

import strawberry
from graphql import GraphQLError
from strawberry.custom_scalar import ScalarDefinition, ScalarWrapper
from strawberry.fastapi import BaseContext
from strawberry.types import Info
from strawberry.types.info import RootValueType

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.db.filters import Filter
from orchestrator.db.sorting import Sort, SortOrder
from orchestrator.utils.vlans import VlanRanges


def serialize_to_string(value: Any) -> str:
    return str(value)


def serialize_vlan(vlan: VlanRanges) -> List[Tuple[int, int]]:
    return vlan.to_list_of_tuples()


class CustomContext(BaseContext):
    def __init__(self, get_current_user: Callable[[], OIDCUserModel], get_opa_decision: Callable[[str], bool]):
        self.errors: list[GraphQLError] = []
        self.get_current_user = get_current_user
        self.get_opa_decision = get_opa_decision
        super().__init__()


CustomInfo = Info[CustomContext, RootValueType]


@strawberry.experimental.pydantic.input(model=Sort)
class GraphqlSort:
    field: str = strawberry.field(description="Field to sort on")
    order: SortOrder = strawberry.field(default=SortOrder.ASC, description="Sort order (ASC or DESC")


@strawberry.experimental.pydantic.input(model=Filter)
class GraphqlFilter:
    field: str = strawberry.field(description="Field to filter on")
    value: str = strawberry.field(description="Value to sort the field on")


JSON = strawberry.scalar(
    NewType("JSON", object),
    description="The `JSON` scalar type represents JSON values as specified by ECMA-404",
    serialize=lambda v: v,
    parse_value=lambda v: v,
)

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

SCALAR_OVERRIDES: dict[object, Any | ScalarWrapper | ScalarDefinition] = {
    dict: JSON,
    VlanRanges: VlanRangesType,
    IPv4Address: IPv4AddressType,
    IPv6Address: IPv6AddressType,
    IPv4Interface: IPv4InterfaceType,
    IPv6Interface: IPv6InterfaceType,
}

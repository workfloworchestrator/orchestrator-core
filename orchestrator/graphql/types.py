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
from typing import Any, NewType, TypeVar

import strawberry
from graphql import GraphQLError
from strawberry.custom_scalar import ScalarDefinition, ScalarWrapper
from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic
from strawberry.scalars import JSON
from strawberry.types import Info
from strawberry.types.info import RootValueType

from nwastdlib.vlans import VlanRanges
from oauth2_lib.fastapi import AuthManager
from oauth2_lib.strawberry import OauthContext
from orchestrator.db.filters import Filter
from orchestrator.db.sorting import Sort, SortOrder
from orchestrator.services.process_broadcast_thread import ProcessDataBroadcastThread

StrawberryPydanticModel = TypeVar("StrawberryPydanticModel", bound=StrawberryTypeFromPydantic)
StrawberryModelType = dict[str, StrawberryPydanticModel]


def serialize_to_string(value: Any) -> str:
    return str(value)


def serialize_vlan(vlan: VlanRanges) -> list[tuple[int, int]]:
    return vlan.to_list_of_tuples()


class OrchestratorContext(OauthContext):
    broadcast_thread: ProcessDataBroadcastThread | None
    graphql_models: StrawberryModelType

    def __init__(
        self,
        auth_manager: AuthManager,
        broadcast_thread: ProcessDataBroadcastThread | None = None,
        graphql_models: StrawberryModelType | None = None,
    ):
        self.errors: list[GraphQLError] = []
        self.broadcast_thread = broadcast_thread
        self.graphql_models = graphql_models or {}
        super().__init__(auth_manager)


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

ScalarOverrideType = dict[object, type | ScalarWrapper | ScalarDefinition]
SCALAR_OVERRIDES: ScalarOverrideType = {
    dict: JSON,
    VlanRanges: VlanRangesType,
    IPv4Address: IPv4AddressType,
    IPv6Address: IPv6AddressType,
    IPv4Interface: IPv4InterfaceType,
    IPv6Interface: IPv6InterfaceType,
    int: IntType,
}


@strawberry.type(description="Generic class to capture errors")
class MutationError:
    message: str = strawberry.field(description="Error message")
    details: str | None = strawberry.field(description="Details of error cause", default=None)


@strawberry.type(description="Error class if a resource couldn't be found (404)")
class NotFoundError(MutationError):  # noqa: N818
    pass

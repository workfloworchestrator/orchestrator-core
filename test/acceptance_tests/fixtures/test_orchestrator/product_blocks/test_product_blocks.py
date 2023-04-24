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


from ipaddress import IPv4Address, IPv6Address
from typing import Union
from uuid import UUID

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


class TestProductBlockInactive(ProductBlockModel, product_block_name="Test Product Block"):
    an_int: Union[int, None] = None
    a_str: Union[str, None] = None
    a_bool: Union[bool, None] = None
    an_uuid: Union[UUID, None] = None
    an_ipv4: Union[IPv4Address, None] = None
    an_ipv6: Union[IPv6Address, None] = None


class TestProductBlockProvisioning(TestProductBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    an_int: int
    a_str: str
    a_bool: Union[bool, None] = None
    an_uuid: UUID
    an_ipv4: Union[IPv4Address, None] = None
    an_ipv6: Union[IPv6Address, None] = None


class TestProductBlock(TestProductBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    an_int: int
    a_str: str
    a_bool: bool
    an_uuid: UUID
    an_ipv4: IPv4Address
    an_ipv6: IPv6Address

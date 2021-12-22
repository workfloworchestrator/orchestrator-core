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

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type, TypeVar

import structlog

from orchestrator.types import SubscriptionLifecycle, strEnum

logger = structlog.get_logger(__name__)


class ProductLifecycle(strEnum):
    ACTIVE = "active"
    PRE_PRODUCTION = "pre production"
    PHASE_OUT = "phase out"
    END_OF_LIFE = "end of life"


_sub_type_per_lifecycle: Dict[Tuple[Type, Optional[SubscriptionLifecycle]], Type] = {}


def register_specialized_type(cls: Type, lifecycle: Optional[List[SubscriptionLifecycle]] = None) -> None:
    if lifecycle:
        for lifecycle_state in lifecycle:
            _sub_type_per_lifecycle[(cls.__base_type__, lifecycle_state)] = cls
    else:
        _sub_type_per_lifecycle[(cls.__base_type__, None)] = cls


def lookup_specialized_type(block: Type, lifecycle: Optional[SubscriptionLifecycle]) -> Type:
    if not hasattr(block, "__base_type__"):
        raise ValueError("Cannot instantiate a class that has no __base_type__ attribute")

    specialized_block = _sub_type_per_lifecycle.get((block.__base_type__, lifecycle), None)
    if specialized_block is None:
        specialized_block = _sub_type_per_lifecycle.get((block.__base_type__, None), None)
    if specialized_block is None:
        specialized_block = block
    return specialized_block


if TYPE_CHECKING:
    from orchestrator.domain.base import SubscriptionModel
else:
    SubscriptionModel = None
    DomainModel = None
T = TypeVar("T", bound=SubscriptionModel)

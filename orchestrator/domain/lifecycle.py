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

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, TypeVar

import strawberry
import structlog

from orchestrator.types import SubscriptionLifecycle, strEnum

logger = structlog.get_logger(__name__)


@strawberry.enum
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


def validate_lifecycle_status(
    product_block_field_name: str, product_block_field_type: Any, lifecycle_status: SubscriptionLifecycle
) -> None:
    specialized_type = lookup_specialized_type(product_block_field_type, lifecycle_status)
    if not issubclass(product_block_field_type, specialized_type):
        raise AssertionError(
            f"The lifecycle status of the type for the field: {product_block_field_name}, {specialized_type.__name__} (based on {product_block_field_type.__name__}) is not suitable for the lifecycle status ({lifecycle_status}) of this model"
        )


if TYPE_CHECKING:
    from orchestrator.domain.base import SubscriptionModel
else:
    SubscriptionModel = None
    DomainModel = None
T = TypeVar("T", bound=SubscriptionModel)

# Copyright 2024-2026 SURF, GÉANT.
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

from enum import IntEnum

from orchestrator.core.domain.base import ProductBlockModel
from orchestrator.core.types import SubscriptionLifecycle
from pydantic import computed_field


class ExampleIntEnum2(IntEnum):
    _1 = 1
    _2 = 2
    _3 = 3
    _4 = 4


class Example2BlockInactive(ProductBlockModel, product_block_name="Example2"):
    example_int_enum_2: ExampleIntEnum2 | None = None


class Example2BlockProvisioning(Example2BlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    example_int_enum_2: ExampleIntEnum2 | None = None

    @computed_field
    @property
    def title(self) -> str:
        # TODO: format correct title string
        return f"{self.name}"


class Example2Block(Example2BlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    example_int_enum_2: ExampleIntEnum2

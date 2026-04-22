# Copyright 2019-2026 SURF, GÉANT.
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

from orchestrator.core.domain.base import ProductBlockModel
from orchestrator.core.types import SubscriptionLifecycle
from pydantic import computed_field

from products.product_blocks.example4sub import Example4SubBlock, Example4SubBlockInactive, Example4SubBlockProvisioning


class Example4BlockInactive(ProductBlockModel, product_block_name="Example4"):
    num_val: int | None = None
    sub_block: Example4SubBlockInactive | None = None


class Example4BlockProvisioning(Example4BlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    num_val: int | None = None
    sub_block: Example4SubBlockProvisioning

    @computed_field
    @property
    def title(self) -> str:
        # TODO: format correct title string
        return f"{self.name}"


class Example4Block(Example4BlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    num_val: int | None = None
    sub_block: Example4SubBlock

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


class Example4SubBlockInactive(ProductBlockModel, product_block_name="Example4Sub"):
    str_val: str | None = None


class Example4SubBlockProvisioning(Example4SubBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    str_val: str | None = None

    @computed_field
    @property
    def title(self) -> str:
        # TODO: format correct title string
        return f"{self.name}"


class Example4SubBlock(Example4SubBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    str_val: str | None = None

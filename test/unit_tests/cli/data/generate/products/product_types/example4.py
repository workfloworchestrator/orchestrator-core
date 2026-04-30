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

from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.types import SubscriptionLifecycle

from products.product_blocks.example4 import Example4Block, Example4BlockInactive, Example4BlockProvisioning


class Example4Inactive(SubscriptionModel, is_base=True):
    example4: Example4BlockInactive


class Example4Provisioning(Example4Inactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    example4: Example4BlockProvisioning


class Example4(Example4Provisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    example4: Example4Block

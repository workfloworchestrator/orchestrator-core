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

from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.types import SubscriptionLifecycle

from products.product_blocks.example1 import Example1Block, Example1BlockInactive, Example1BlockProvisioning


class FixedInput1(IntEnum):
    _1 = 1
    _10 = 10
    _100 = 100
    _1000 = 1000


class Example1Inactive(SubscriptionModel, is_base=True):
    fixed_input_1: FixedInput1
    example1: Example1BlockInactive


class Example1Provisioning(Example1Inactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    fixed_input_1: FixedInput1
    example1: Example1BlockProvisioning


class Example1(Example1Provisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    fixed_input_1: FixedInput1
    example1: Example1Block

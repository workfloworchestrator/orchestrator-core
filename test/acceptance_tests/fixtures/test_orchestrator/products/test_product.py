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


from test_orchestrator.product_blocks.test_product_blocks import (
    TestProductBlock,
    TestProductBlockInactive,
    TestProductBlockProvisioning,
)

from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


class TestProductInactive(SubscriptionModel, is_base=True):
    testproduct: TestProductBlockInactive


class TestProductProvisioning(TestProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    testproduct: TestProductBlockProvisioning


class TestProduct(TestProductProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    testproduct: TestProductBlock

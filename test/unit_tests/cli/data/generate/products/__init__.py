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

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY

from products.product_types.example2 import Example2

SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "example2": Example2,
        },
)  # fmt:skip
from products.product_types.example1 import Example1

SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "example1 1": Example1,
        "example1 10": Example1,
        "example1 100": Example1,
        "example1 1000": Example1,
        },
)  # fmt:skip
from products.product_types.example4 import Example4

SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "example4": Example4,
        },
)  # fmt:skip

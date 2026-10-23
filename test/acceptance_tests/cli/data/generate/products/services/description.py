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
from functools import singledispatch

from orchestrator.core.domain.base import ProductBlockModel, ProductModel, SubscriptionModel
from orchestrator.core.utils.singledispatch import single_dispatch_base

from products.product_types.example1 import Example1Provisioning
from products.product_types.example2 import Example2Provisioning
from products.product_types.example4 import Example4Provisioning


@singledispatch
def description(model: ProductModel | ProductBlockModel | SubscriptionModel) -> str:
    """Build subscription description (generic function).

    Specific implementations of this generic function will specify the model types they work on.

    Args:
        model: Domain model for which to construct a description.

    Returns:
        The constructed description.

    Raises:
        TypeError: in case a specific implementation could not be found. The domain model it was called for will be
            part of the error message.

    """
    return single_dispatch_base(description, model)


@description.register
def _(example2: Example2Provisioning) -> str:
    # TODO: implement a product specific description
    return f"{example2.product.name} subscription"


@description.register
def _(example1: Example1Provisioning) -> str:
    # TODO: implement a product specific description
    return f"{example1.product.name} subscription"


@description.register
def _(example4: Example4Provisioning) -> str:
    # TODO: implement a product specific description
    return f"{example4.product.name} subscription"

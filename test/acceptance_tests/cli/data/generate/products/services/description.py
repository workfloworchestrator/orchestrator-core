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

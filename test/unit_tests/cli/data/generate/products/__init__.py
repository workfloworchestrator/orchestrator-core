from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

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

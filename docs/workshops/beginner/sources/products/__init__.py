from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

from products.product_types.user import User
from products.product_types.user_group import UserGroup

# Register models to actual definitions for deserialization purposes
SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "User Group": UserGroup,
        "User internal": User,
        "User external": User,
    }
)

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle

from products.product_blocks.user_group import UserGroupBlock, UserGroupBlockInactive, UserGroupBlockProvisioning


class UserBlockInactive(ProductBlockModel, lifecycle=[SubscriptionLifecycle.INITIAL], product_block_name="UserBlock"):
    group: UserGroupBlockInactive
    username: str | None = None
    age: int | None = None
    user_id: int | None = None


class UserBlockProvisioning(UserBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    group: UserGroupBlockProvisioning
    username: str
    age: int | None = None
    user_id: int | None = None


class UserBlock(UserBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    group: UserGroupBlock
    username: str
    age: int | None = None
    user_id: int

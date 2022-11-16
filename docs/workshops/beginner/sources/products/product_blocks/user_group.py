from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


class UserGroupBlockInactive(
    ProductBlockModel, lifecycle=[SubscriptionLifecycle.INITIAL], product_block_name="UserGroupBlock"
):
    group_name: str | None = None
    group_id: int | None = None


class UserGroupBlockProvisioning(UserGroupBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    group_name: str
    group_id: int | None = None


class UserGroupBlock(UserGroupBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    group_name: str
    group_id: int

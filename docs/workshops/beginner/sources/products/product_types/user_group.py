from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle

from products.product_blocks.user_group import UserGroupBlock, UserGroupBlockInactive, UserGroupBlockProvisioning


class UserGroupInactive(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.INITIAL]):
    user_group: UserGroupBlockInactive


class UserGroupProvisioning(UserGroupInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    user_group: UserGroupBlockProvisioning


class UserGroup(UserGroupProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    user_group: UserGroupBlock

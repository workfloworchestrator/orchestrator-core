from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle, strEnum

from products.product_blocks.user import UserBlock, UserBlockInactive, UserBlockProvisioning


class Affiliation(strEnum):
    internal = "internal"
    external = "external"


class UserInactive(SubscriptionModel, is_base=True):
    affiliation: Affiliation
    user: UserBlockInactive


class UserProvisioning(UserInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    affiliation: Affiliation
    user: UserBlockProvisioning


class User(UserProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    affiliation: Affiliation
    user: UserBlock

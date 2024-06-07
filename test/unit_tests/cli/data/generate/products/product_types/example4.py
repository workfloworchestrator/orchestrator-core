from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle

from products.product_blocks.example4 import Example4Block, Example4BlockInactive, Example4BlockProvisioning


class Example4Inactive(SubscriptionModel, is_base=True):
    example4: Example4BlockInactive


class Example4Provisioning(Example4Inactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    example4: Example4BlockProvisioning


class Example4(Example4Provisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    example4: Example4Block

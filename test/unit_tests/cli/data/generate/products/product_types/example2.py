from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle

from products.product_blocks.example2 import Example2Block, Example2BlockInactive, Example2BlockProvisioning


class Example2Inactive(SubscriptionModel, is_base=True):
    example2: Example2BlockInactive


class Example2Provisioning(Example2Inactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    example2: Example2BlockProvisioning


class Example2(Example2Provisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    example2: Example2Block

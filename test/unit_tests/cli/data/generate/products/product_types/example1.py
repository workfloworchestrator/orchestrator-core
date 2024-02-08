from enum import IntEnum

from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle

from products.product_blocks.example1 import Example1Block, Example1BlockInactive, Example1BlockProvisioning


class FixedInput1(IntEnum):
    _1 = 1
    _10 = 10
    _100 = 100
    _1000 = 1000


class Example1Inactive(SubscriptionModel, is_base=True):
    fixed_input_1: FixedInput1
    example1: Example1BlockInactive


class Example1Provisioning(Example1Inactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    fixed_input_1: FixedInput1
    example1: Example1BlockProvisioning


class Example1(Example1Provisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    fixed_input_1: FixedInput1
    example1: Example1Block

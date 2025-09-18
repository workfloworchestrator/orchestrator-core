from orchestrator.domain.base import SubscriptionModel

from .blocks import BasicBlock, ComputedBlock, ContainerListBlock, OuterBlock


class SimpleSubscription(SubscriptionModel, is_base=True):
    """Simple subscription with direct block access."""

    basic_block: BasicBlock


class NestedSubscription(SubscriptionModel, is_base=True):
    """Subscription with deeply nested blocks."""

    outer_block: OuterBlock


class ComplexSubscription(SubscriptionModel, is_base=True):
    """Root subscription model for comprehensive testing."""

    container_list: ContainerListBlock


class ComputedPropertySubscription(SubscriptionModel, is_base=True):
    """Subscription containing a block with computed property."""

    device: ComputedBlock

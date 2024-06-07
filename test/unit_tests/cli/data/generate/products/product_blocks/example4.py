from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle
from pydantic import computed_field

from products.product_blocks.example4sub import Example4SubBlock, Example4SubBlockInactive, Example4SubBlockProvisioning


class Example4BlockInactive(ProductBlockModel, product_block_name="Example4"):
    num_val: int | None = None
    sub_block: Example4SubBlockInactive | None = None


class Example4BlockProvisioning(Example4BlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    num_val: int | None = None
    sub_block: Example4SubBlockProvisioning

    @computed_field
    @property
    def title(self) -> str:
        # TODO: format correct title string
        return f"{self.name}"


class Example4Block(Example4BlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    num_val: int | None = None
    sub_block: Example4SubBlock

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle
from pydantic import computed_field


class Example4SubBlockInactive(ProductBlockModel, product_block_name="Example4 Sub"):
    str_val: str | None = None


class Example4SubBlockProvisioning(Example4SubBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    str_val: str | None = None

    @computed_field
    @property
    def title(self) -> str:
        # TODO: format correct title string
        return f"{self.name}"


class Example4SubBlock(Example4SubBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    str_val: str | None = None

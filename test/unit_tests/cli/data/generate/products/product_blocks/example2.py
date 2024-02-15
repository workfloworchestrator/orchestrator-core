from enum import IntEnum

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle
from pydantic import computed_field


class ExampleIntEnum2(IntEnum):
    _1 = 1
    _2 = 2
    _3 = 3
    _4 = 4


class Example2BlockInactive(ProductBlockModel, product_block_name="Example2"):
    example_int_enum_2: ExampleIntEnum2 | None = None


class Example2BlockProvisioning(Example2BlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    example_int_enum_2: ExampleIntEnum2 | None = None

    @computed_field
    @property
    def title(self) -> str:
        # TODO: format correct title string
        return f"{self.name}"


class Example2Block(Example2BlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    example_int_enum_2: ExampleIntEnum2

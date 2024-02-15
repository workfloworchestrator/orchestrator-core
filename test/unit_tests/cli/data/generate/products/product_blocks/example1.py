from enum import StrEnum
from ipaddress import IPv4Address
from typing import Annotated

from annotated_types import Ge, Le, Len
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SI, SubscriptionLifecycle
from pydantic import computed_field

from products.product_blocks.example2 import Example2Block, Example2BlockInactive, Example2BlockProvisioning


class ExampleStrEnum1(StrEnum):
    option1 = "option1"
    option2 = "option2"
    option3 = "option3"


ListOfEight = Annotated[list[SI], Len(min_length=1, max_length=8)]


AnnotatedInt = Annotated[int, Ge(1), Le(32_767)]


class Example1BlockInactive(ProductBlockModel, product_block_name="Example1"):
    example_str_enum_1: ExampleStrEnum1 = ExampleStrEnum1.option2
    example2: Example2BlockInactive | None = None
    unmodifiable_str: str | None = None
    eight: ListOfEight[Example2BlockInactive]
    modifiable_boolean: bool | None = False
    annotated_int: AnnotatedInt | None = None
    imported_type: IPv4Address | None = None
    always_optional_str: str | None = None


class Example1BlockProvisioning(Example1BlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    example_str_enum_1: ExampleStrEnum1
    example2: Example2BlockProvisioning
    unmodifiable_str: str
    eight: ListOfEight[Example2BlockProvisioning]
    modifiable_boolean: bool
    annotated_int: AnnotatedInt | None = None
    imported_type: IPv4Address | None = None
    always_optional_str: str | None = None

    @computed_field
    @property
    def title(self) -> str:
        # TODO: format correct title string
        return f"{self.name}"


class Example1Block(Example1BlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    example_str_enum_1: ExampleStrEnum1
    example2: Example2Block
    unmodifiable_str: str
    eight: ListOfEight[Example2Block]
    modifiable_boolean: bool
    annotated_int: AnnotatedInt
    imported_type: IPv4Address
    always_optional_str: str | None = None

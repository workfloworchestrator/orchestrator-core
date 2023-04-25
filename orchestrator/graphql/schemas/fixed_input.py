import strawberry

from orchestrator.schemas.fixed_input import FixedInputConfigurationItemSchema, FixedInputSchema, TagConfig


@strawberry.experimental.pydantic.type(model=FixedInputSchema, all_fields=True)
class FixedInput:
    pass


@strawberry.experimental.pydantic.type(model=FixedInputConfigurationItemSchema, all_fields=True)
class FixedInputConfigurationItem:
    pass


@strawberry.input
class FixedInputConfigurationInputType:
    fixed_inputs: list[FixedInputConfigurationItem]
    by_tag: TagConfig

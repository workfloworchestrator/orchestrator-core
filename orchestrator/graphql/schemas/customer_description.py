import strawberry

from orchestrator.schemas import SubscriptionDescriptionSchema


@strawberry.experimental.pydantic.type(model=SubscriptionDescriptionSchema, all_fields=True)
class CustomerDescription:
    pass

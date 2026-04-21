import strawberry

from orchestrator.core.schemas import SubscriptionDescriptionSchema


@strawberry.experimental.pydantic.type(model=SubscriptionDescriptionSchema, all_fields=True)
class CustomerDescription:
    pass

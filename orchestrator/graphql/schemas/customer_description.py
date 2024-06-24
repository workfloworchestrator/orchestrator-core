from orchestrator.graphql.utils.modify_class import strawberry_orchestrator_type
from orchestrator.schemas import SubscriptionDescriptionSchema


@strawberry_orchestrator_type(model=SubscriptionDescriptionSchema, all_fields=True)
class CustomerDescription:
    pass

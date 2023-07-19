import strawberry

from orchestrator.graphql.schemas.errors import Error


@strawberry.type
class DefaultCustomerType:
    id: str


DefaultCustomerResponse = strawberry.union("DefaultCustomerResponse", types=(DefaultCustomerType, Error))

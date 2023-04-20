import strawberry

from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.schemas.product_block import ProductBlockEnrichedSchema


@strawberry.experimental.pydantic.type(model=ProductBlockEnrichedSchema, all_fields=True)
class ProductBlockBase:
    pass


class ProductBlockType(ProductBlockBase):
    resource_types: list[ResourceType] | None

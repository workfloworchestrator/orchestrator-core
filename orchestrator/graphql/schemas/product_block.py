import strawberry

from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.schemas.product_block import ProductBlockSchema


@strawberry.experimental.pydantic.type(
    model=ProductBlockSchema,
    fields=[
        "product_block_id",
        "name",
        "description",
        "tag",
        "status",
        "created_at",
        "end_date",
    ],
)
class ProductBlock:
    resource_types: list[ResourceType] | None

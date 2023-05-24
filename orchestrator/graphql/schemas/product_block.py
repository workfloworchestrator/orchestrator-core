from typing import Optional

import strawberry

from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.schemas.product_block import ProductBlockSchema


@strawberry.experimental.pydantic.type(model=ProductBlockSchema)
class ProductBlock:
    product_block_id: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    tag: strawberry.auto
    status: strawberry.auto
    created_at: strawberry.auto
    end_date: strawberry.auto
    resource_types: Optional[list[ResourceType]]

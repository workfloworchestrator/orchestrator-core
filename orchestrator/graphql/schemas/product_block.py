from typing import Annotated

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
    resource_types: list[ResourceType]

    @strawberry.field(description="Return all product blocks that this product block depends on")  # type: ignore
    async def depends_on(self) -> list[Annotated["ProductBlock", strawberry.lazy(".product_block")]]:
        return [ProductBlock.from_pydantic(product_block) for product_block in self._original_model.depends_on]  # type: ignore

    @strawberry.field(description="Return all product blocks that uses this product block")  # type: ignore
    async def in_use_by(self) -> list[Annotated["ProductBlock", strawberry.lazy(".product_block")]]:
        return [ProductBlock.from_pydantic(product_block) for product_block in self._original_model.in_use_by]  # type: ignore

from typing import TYPE_CHECKING, Annotated

import strawberry

from orchestrator.db import ResourceTypeTable
from orchestrator.graphql.schemas.helpers import get_original_model
from orchestrator.schemas.resource_type import ResourceTypeSchema

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.product_block import ProductBlock


@strawberry.experimental.pydantic.type(model=ResourceTypeSchema, all_fields=True)
class ResourceType:
    @strawberry.field(description="Return all product blocks that make use of this resource type")  # type: ignore
    async def product_blocks(self) -> list[Annotated["ProductBlock", strawberry.lazy(".product_block")]]:
        from orchestrator.graphql.schemas.product_block import ProductBlock

        model = get_original_model(self, ResourceTypeTable)
        return [ProductBlock.from_pydantic(product_block) for product_block in model.product_blocks]

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

import strawberry
from sqlalchemy import select

from orchestrator.db import db
from orchestrator.db.models import SubscriptionTable
from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.schemas.product_block import ProductBlockSchema

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.subscription import SubscriptionInterface


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


@strawberry.type
class BaseProductBlockType:
    owner_subscription_id: UUID

    @strawberry.field(description="resolve to subscription of the product block")
    async def subscription(
        self, info: OrchestratorInfo
    ) -> Annotated["SubscriptionInterface", strawberry.lazy(".subscription")] | None:
        from orchestrator.graphql.resolvers.subscription import format_subscription

        stmt = select(SubscriptionTable).where(SubscriptionTable.subscription_id == self.owner_subscription_id)

        if subscription := db.session.scalar(stmt):
            return format_subscription(info, subscription)
        return None

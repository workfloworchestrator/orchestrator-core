# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import strawberry
from sqlalchemy import select

from orchestrator.core.db import ProductBlockTable, db
from orchestrator.core.db.models import SubscriptionTable
from orchestrator.core.graphql.schemas.helpers import get_original_model
from orchestrator.core.graphql.schemas.resource_type import ResourceType
from orchestrator.core.graphql.types import OrchestratorInfo
from orchestrator.core.schemas.product_block import ProductBlockSchema

if TYPE_CHECKING:
    from orchestrator.core.graphql.schemas.subscription import SubscriptionInterface


@strawberry.experimental.pydantic.type(model=ProductBlockSchema)
class ProductBlock:
    product_block_id: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    tag: strawberry.auto
    status: strawberry.auto
    created_at: strawberry.auto
    end_date: strawberry.auto

    @strawberry.field(description="Return all product blocks that this product block depends on")  # type: ignore
    async def depends_on(self) -> list[Annotated["ProductBlock", strawberry.lazy(".product_block")]]:
        return [ProductBlock.from_pydantic(product_block) for product_block in self._original_model.depends_on]  # type: ignore

    @strawberry.field(description="Return all product blocks that uses this product block")  # type: ignore
    async def in_use_by(self) -> list[Annotated["ProductBlock", strawberry.lazy(".product_block")]]:
        return [ProductBlock.from_pydantic(product_block) for product_block in self._original_model.in_use_by]  # type: ignore

    @strawberry.field(description="Return workflows")  # type: ignore
    async def resource_types(self) -> list[Annotated["ResourceType", strawberry.lazy(".resource_type")]]:
        from orchestrator.core.graphql.schemas.resource_type import ResourceType

        model = get_original_model(self, ProductBlockTable)

        return [ResourceType.from_pydantic(i) for i in model.resource_types]


async def owner_subscription_resolver(
    root: Any, info: OrchestratorInfo
) -> Annotated["SubscriptionInterface", strawberry.lazy(".subscription")] | None:
    from orchestrator.core.graphql.resolvers.subscription import format_subscription

    stmt = select(SubscriptionTable).where(SubscriptionTable.subscription_id == root.owner_subscription_id)

    if subscription := db.session.scalar(stmt):
        return await format_subscription(info, subscription)
    return None


@strawberry.interface
class BaseProductBlockType:
    subscription_instance_id: UUID
    owner_subscription_id: UUID
    name: str | None = None
    label: str | None = None
    title: str | None = None
    subscription: Annotated["SubscriptionInterface", strawberry.lazy(".subscription")] | None = strawberry.field(
        description="resolve to subscription of the product block", resolver=owner_subscription_resolver
    )

from typing import TYPE_CHECKING, Annotated

import strawberry
from strawberry.federation.schema_directives import Key
from strawberry.unset import UNSET

from oauth2_lib.strawberry import authenticated_field
from orchestrator.domain.base import ProductModel
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.fixed_input import FixedInput
from orchestrator.graphql.schemas.product_block import ProductBlock
from orchestrator.graphql.schemas.workflow import Workflow
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.schemas.product import ProductSchema

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.subscription import SubscriptionInterface


federation_key_directives = [Key(fields="productId", resolvable=UNSET)]


@strawberry.experimental.pydantic.type(model=ProductSchema, directives=federation_key_directives)
class ProductType:
    product_id: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    product_type: strawberry.auto
    status: strawberry.auto
    tag: strawberry.auto
    created_at: strawberry.auto
    end_date: strawberry.auto
    product_blocks: list[ProductBlock]
    fixed_inputs: list[FixedInput]
    workflows: list[Workflow]

    @strawberry.field(description="Returns the product type")  # type: ignore
    async def type(self) -> str:
        return self.product_type

    @authenticated_field(description="Returns list of subscriptions of the product type")  # type: ignore
    async def subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        filter_by_with_related_subscriptions = (filter_by or []) + [GraphqlFilter(field="product", value=self.name)]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)


@strawberry.experimental.pydantic.type(model=ProductModel, all_fields=True)
class ProductModelGraphql:
    @strawberry.field(description="Returns the product type")  # type: ignore
    async def type(self) -> str:
        return self.product_type  # type: ignore

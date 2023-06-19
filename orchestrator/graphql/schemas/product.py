from typing import TYPE_CHECKING, Annotated, Union

import strawberry
from oauth2_lib.graphql_authentication import authenticated_field

from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.fixed_input import FixedInput
from orchestrator.graphql.schemas.product_block import ProductBlock
from orchestrator.graphql.schemas.workflow import Workflow
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort
from orchestrator.schemas.product import ProductSchema

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.subscription import SubscriptionType


@strawberry.experimental.pydantic.type(model=ProductSchema)
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

    @authenticated_field(description="Returns list of subscriptions of the product type")  # type: ignore
    async def subscriptions(
        self,
        info: CustomInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionType", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        filter_by_with_related_subscriptions = (filter_by or []) + [GraphqlFilter(field="product", value=self.name)]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)

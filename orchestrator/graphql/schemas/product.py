from typing import TYPE_CHECKING, Annotated, Iterable

import strawberry
from strawberry import UNSET
from strawberry.federation.schema_directives import Key

from oauth2_lib.strawberry import authenticated_field
from orchestrator.db import ProductBlockTable, ProductTable
from orchestrator.domain.base import ProductModel
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.fixed_input import FixedInput
from orchestrator.graphql.schemas.helpers import get_original_model
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

    @strawberry.field(description="Returns list of all nested productblock names")  # type: ignore
    async def all_pb_names(self) -> list[str]:

        model = get_original_model(self, ProductTable)

        def get_all_pb_names(product_blocks: list[ProductBlockTable]) -> Iterable[str]:
            for product_block in product_blocks:
                yield product_block.name

                if product_block.depends_on:
                    yield from get_all_pb_names(product_block.depends_on)

        names: list[str] = list(get_all_pb_names(model.product_blocks))
        names.sort()

        return names

    @strawberry.field(description="Return product blocks")  # type: ignore
    async def product_blocks(self) -> list[Annotated["ProductBlock", strawberry.lazy(".product_block")]]:
        from orchestrator.graphql.schemas.product_block import ProductBlock

        model = get_original_model(self, ProductTable)

        return [ProductBlock.from_pydantic(i) for i in model.product_blocks]

    @strawberry.field(description="Return fixed inputs")  # type: ignore
    async def fixed_inputs(self) -> list[Annotated["FixedInput", strawberry.lazy(".fixed_input")]]:
        from orchestrator.graphql.schemas.fixed_input import FixedInput

        model = get_original_model(self, ProductTable)

        return [FixedInput.from_pydantic(i) for i in model.fixed_inputs]

    @strawberry.field(description="Return workflows")  # type: ignore
    async def workflows(self) -> list[Annotated["Workflow", strawberry.lazy(".workflow")]]:
        from orchestrator.graphql.schemas.workflow import Workflow

        model = get_original_model(self, ProductTable)

        return [Workflow.from_pydantic(i) for i in model.workflows]


@strawberry.experimental.pydantic.type(model=ProductModel, all_fields=True)
class ProductModelGraphql:
    @strawberry.field(description="Returns the product type")  # type: ignore
    async def type(self) -> str:
        return self.product_type  # type: ignore

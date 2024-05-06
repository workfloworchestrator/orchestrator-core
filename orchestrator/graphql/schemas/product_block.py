from typing import TYPE_CHECKING, Annotated, Any, Callable, Iterable, Literal
from uuid import UUID

import strawberry

from orchestrator.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.schemas.product_block import ProductBlockSchema
from pydantic_forms.types import UUIDstr

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


async def owner_subscription_resolver(
    root: Any, info: OrchestratorInfo
) -> Annotated["SubscriptionInterface", strawberry.lazy(".subscription")] | None:
    from orchestrator.graphql.resolvers.subscription import resolve_subscription

    return resolve_subscription(root.owner_subscription_id, info)  # type: ignore


RelationLiteral = Literal["in_use_by", "depends_on", "subscriptions"]
BlockRelationLiteral = ["in_use_by", "depends_on"]


def get_subscription_ids(root: Any, relation: RelationLiteral) -> Iterable[UUIDstr]:
    values = getattr(root._original_model, relation, [])
    if relation in BlockRelationLiteral:
        return map(lambda x: UUIDstr(getattr(x, "subscription_id", "")), values)
    return map(lambda x: UUIDstr(x), values)


def related_subscriptions_resolver(relation: RelationLiteral) -> Callable[[Any], list[UUID]]:
    async def subscriptions_resolver(
        root: Any,
        info: OrchestratorInfo,
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        subscription_ids = list(get_subscription_ids(root, relation))
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionId", value="|".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)  # type: ignore

    return subscriptions_resolver  # type: ignore


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
    in_use_by_subscriptions: Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]] = (
        strawberry.field(  # type: ignore
            description="resolve to in use by subscriptions of the product block",
            resolver=related_subscriptions_resolver("in_use_by"),
        )
    )
    depends_on_subscriptions: Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]] = (
        strawberry.field(  # type: ignore
            description="resolve to depends on subscriptions of the product block",
            resolver=related_subscriptions_resolver("depends_on"),
        )
    )

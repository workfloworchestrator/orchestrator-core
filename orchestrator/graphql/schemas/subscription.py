from datetime import datetime
from itertools import count
from typing import Annotated, Any, Generator, List, Optional, Union
from uuid import UUID

import strawberry
from oauth2_lib.graphql_authentication import authenticated_field
from strawberry.scalars import JSON

from orchestrator.db.models import SubscriptionTable
from orchestrator.domain.base import SubscriptionModel
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers.process import resolve_processes
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.product import ProductSchema
from orchestrator.schemas.subscription_descriptions import SubscriptionDescriptionSchema
from orchestrator.services.subscriptions import build_extended_domain_model
from orchestrator.utils.helpers import to_camel


@strawberry.type
class SubscriptionProductBlock:
    id: int
    parent: int | None
    owner_subscription_id: UUID
    resource_types: JSON


def is_product_block(candidate: Any) -> bool:
    match candidate:
        case dict():
            # TODO: also filter on tag (needs addition of tag in orchestrator endpoint)
            # NOTE: this crosses subscription boundaries. If needed we can add an additional filter to limit that.
            return candidate.get("owner_subscription_id", None)
        case _:
            return False


def get_all_product_blocks(subscription: dict[str, Any], _tags: list[str] | None) -> list[dict[str, Any]]:
    gen_id = count()

    def locate_product_block(candidate: dict[str, Any]) -> Generator:
        def new_product_block(item: dict[str, Any]) -> Generator:
            enriched_item = item | {"id": next(gen_id), "parent": candidate.get("id")}
            yield enriched_item
            yield from locate_product_block(enriched_item)

        for value in candidate.values():
            if is_product_block(value):
                yield from new_product_block(value)
            elif isinstance(value, list):
                for item in value:
                    if is_product_block(item):
                        yield from new_product_block(item)

    return list(locate_product_block(subscription))


@strawberry.experimental.pydantic.type(model=SubscriptionDescriptionSchema, all_fields=True)
class SubscriptionDescriptionType:
    pass


class SubscriptionGraphqlSchema(OrchestratorBaseModel):
    subscription_id: UUID
    product: ProductSchema
    customer_descriptions: List[Optional[SubscriptionDescriptionSchema]] = []  # type: ignore
    description: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    product_id: UUID
    customer_id: UUID
    status: str
    insync: bool
    note: Optional[str]
    name: Optional[str]
    tag: Optional[str]


@strawberry.experimental.pydantic.type(model=SubscriptionGraphqlSchema, all_fields=True)
class SubscriptionType:
    subscription_id: strawberry.auto

    @strawberry.field(description="Return all products blocks that are part of a subscription")
    async def product_blocks(
        self, tags: list[str] | None = None, resource_types: list[str] | None = None
    ) -> list[SubscriptionProductBlock]:
        subscription_model = SubscriptionModel.from_subscription(self.subscription_id)  # type: ignore
        subscription = build_extended_domain_model(subscription_model)

        def to_product_block(product_block: dict[str, Any]) -> SubscriptionProductBlock:
            def is_resource_type(candidate: Any) -> bool:
                return isinstance(candidate, bool | str | int | float | None)

            def requested_resource_type(key: str) -> bool:
                return not resource_types or key in resource_types

            def included(key: str, value: Any) -> bool:
                return is_resource_type(value) and requested_resource_type(key) and key not in ("id", "parent")

            return SubscriptionProductBlock(
                id=product_block["id"],
                parent=product_block.get("parent"),
                owner_subscription_id=product_block["owner_subscription_id"],
                resource_types={to_camel(k): v for k, v in product_block.items() if included(k, v)},
            )

        product_blocks = (
            to_product_block(product_block) for product_block in get_all_product_blocks(subscription, tags)
        )
        return [product_block for product_block in product_blocks if product_block.resource_types]

    @authenticated_field(description="Returns list of processes of the subscription")
    async def processes(
        self,
        info: CustomInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[ProcessType]:
        filter_by = filter_by or [] + [GraphqlFilter(field="subscriptionId", value=str(self.subscription_id))]  # type: ignore
        return await resolve_processes(info, filter_by, sort_by, first, after)

    @authenticated_field(description="Returns list of subscriptions that use this subscription")
    async def in_use_by_subscriptions(
        self,
        info: CustomInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionType", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscription
        from orchestrator.services.subscriptions import query_in_use_by_subscriptions

        in_use_by_query = query_in_use_by_subscriptions(self.subscription_id)
        query_results = in_use_by_query.with_entities(SubscriptionTable.subscription_id).all()
        subscription_ids = ",".join([str(s.subscription_id) for s in query_results])
        filter_by = (filter_by or []) + [GraphqlFilter(field="subscriptionIds", value=subscription_ids)]  # type: ignore
        return await resolve_subscription(info, filter_by, sort_by, first, after)

    @authenticated_field(description="Returns list of subscriptions that this subscription depends on")
    async def depends_on_subscriptions(
        self,
        info: CustomInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionType", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscription
        from orchestrator.services.subscriptions import query_depends_on_subscriptions

        depends_on_query = query_depends_on_subscriptions(self.subscription_id)
        query_results = depends_on_query.with_entities(SubscriptionTable.subscription_id).all()
        subscription_ids = ",".join([str(s.subscription_id) for s in query_results])
        filter_by = (filter_by or []) + [GraphqlFilter(field="subscriptionIds", value=subscription_ids)]  # type: ignore
        return await resolve_subscription(info, filter_by, sort_by, first, after)

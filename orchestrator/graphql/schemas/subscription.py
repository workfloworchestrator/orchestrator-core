from datetime import datetime
from typing import Annotated, Optional, Union
from uuid import UUID

import strawberry

from oauth2_lib.strawberry import authenticated_field
from orchestrator.db.models import FixedInputTable, SubscriptionTable
from orchestrator.domain.base import SubscriptionModel
from orchestrator.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.graphql.resolvers.process import resolve_processes
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.schemas.product import ProductModelGraphql
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.get_subscription_product_blocks import (
    SubscriptionProductBlock,
    get_subscription_product_blocks,
)
from orchestrator.types import SubscriptionLifecycle


@strawberry.federation.interface(description="Virtual base interface for subscriptions", keys=["subscriptionId"])
class SubscriptionInterface:
    subscription_id: UUID
    product: ProductModelGraphql
    description: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: SubscriptionLifecycle
    insync: bool
    note: Optional[str]

    @strawberry.field(description="Return all products blocks that are part of a subscription")  # type: ignore
    async def product_blocks(
        self, tags: Optional[list[str]] = None, resource_types: Optional[list[str]] = None
    ) -> list[SubscriptionProductBlock]:
        return await get_subscription_product_blocks(self.subscription_id, tags, resource_types)

    @strawberry.field(description="Return fixed inputs")  # type: ignore
    async def fixed_inputs(self) -> JSON:
        fixed_inputs: list[FixedInputTable] = FixedInputTable.query.filter(
            FixedInputTable.product_id == self.product.product_id  # type: ignore
        ).all()
        return {fi.name: fi.value for fi in fixed_inputs}

    @authenticated_field(description="Returns list of processes of the subscription")  # type: ignore
    async def processes(
        self,
        info: OrchestratorInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[ProcessType]:
        filter_by_with_related_processes = (filter_by or []) + [
            GraphqlFilter(field="subscriptionId", value=str(self.subscription_id))
        ]
        return await resolve_processes(info, filter_by_with_related_processes, sort_by, first, after)

    @authenticated_field(description="Returns list of subscriptions that use this subscription")  # type: ignore
    async def in_use_by_subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions
        from orchestrator.services.subscriptions import query_in_use_by_subscriptions

        in_use_by_query = query_in_use_by_subscriptions(self.subscription_id)
        query_results = in_use_by_query.with_entities(SubscriptionTable.subscription_id).all()
        subscription_ids = [str(s.subscription_id) for s in query_results]
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionIds", value=",".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)

    @authenticated_field(description="Returns list of subscriptions that this subscription depends on")  # type: ignore
    async def depends_on_subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions
        from orchestrator.services.subscriptions import query_depends_on_subscriptions

        depends_on_query = query_depends_on_subscriptions(self.subscription_id)
        query_results = depends_on_query.with_entities(SubscriptionTable.subscription_id).all()
        subscription_ids = [str(s.subscription_id) for s in query_results]
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionIds", value=",".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)


@strawberry.experimental.pydantic.type(model=SubscriptionModel, all_fields=True)
class SubscriptionPydantic(SubscriptionInterface):
    pass


@strawberry.federation.type(description="Virtual base class for subscriptions", keys=["subscriptionId"])
class Subscription(SubscriptionPydantic):
    def from_pydantic(model: SubscriptionModel) -> "Subscription":  # type: ignore
        graphql_model = SubscriptionPydantic.from_pydantic(model)
        graphql_model.__class__ = Subscription
        return graphql_model  # type: ignore

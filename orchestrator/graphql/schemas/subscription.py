from datetime import datetime
from typing import Annotated, Optional, Type, Union
from uuid import UUID

import strawberry
from pydantic import BaseModel
from sqlalchemy import select
from strawberry.federation.schema_directives import Key
from strawberry.unset import UNSET

from oauth2_lib.strawberry import authenticated_field
from orchestrator.db import FixedInputTable, ProductTable, SubscriptionTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.graphql.resolvers.process import resolve_processes
from orchestrator.graphql.schemas.default_customer import DefaultCustomerType
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.schemas.product import ProductModelGraphql
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.get_subscription_product_blocks import (
    ProductBlockInstance,
    get_subscription_product_blocks,
)
from orchestrator.services.subscriptions import (
    get_subscription_metadata,
)
from orchestrator.settings import app_settings
from orchestrator.types import SubscriptionLifecycle

federation_key_directives = [Key(fields="subscriptionId", resolvable=UNSET)]

MetadataDict: dict[str, Optional[Type[BaseModel]]] = {"metadata": None}
static_metadata_schema = {"title": "SubscriptionMetadata", "type": "object", "properties": {}, "definitions": {}}


@strawberry.federation.interface(description="Virtual base interface for subscriptions", keys=["subscriptionId"])
class SubscriptionInterface:
    subscription_id: UUID
    customer_id: str
    product: ProductModelGraphql
    description: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: SubscriptionLifecycle
    insync: bool
    note: Optional[str]

    @strawberry.field(name="_schema", description="Return all products block instances of a subscription as JSON Schema")  # type: ignore
    async def schema(self) -> dict:
        product_type_stmt = (
            select(ProductTable.name)
            .join(SubscriptionTable)
            .where(SubscriptionTable.subscription_id == self.subscription_id)
        )
        product_name = db.session.execute(product_type_stmt).scalar_one_or_none()
        subscription_model = SUBSCRIPTION_MODEL_REGISTRY.get(product_name or "")
        subscription_base_model = getattr(subscription_model, "__base_type__", None) if subscription_model else None
        return subscription_base_model.schema() if subscription_base_model else {}

    @strawberry.field(description="Return all products block instances of a subscription")  # type: ignore
    async def product_block_instances(
        self, tags: Optional[list[str]] = None, resource_types: Optional[list[str]] = None
    ) -> list[ProductBlockInstance]:
        return await get_subscription_product_blocks(self.subscription_id, tags, resource_types)

    @strawberry.field(description="Return all products blocks that are part of a subscription", deprecation_reason="changed to product_block_instances")  # type: ignore
    async def product_blocks(
        self, tags: Optional[list[str]] = None, resource_types: Optional[list[str]] = None
    ) -> list[ProductBlockInstance]:
        return await get_subscription_product_blocks(self.subscription_id, tags, resource_types)

    @strawberry.field(description="Return fixed inputs")  # type: ignore
    async def fixed_inputs(self) -> strawberry.scalars.JSON:
        stmt = select(FixedInputTable).where(FixedInputTable.product_id == self.product.product_id)  # type: ignore
        fixed_inputs = db.session.scalars(stmt).all()
        return [{"field": fi.name, "value": fi.value} for fi in fixed_inputs]

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

    @strawberry.field(description="Returns customer of a subscription")  # type: ignore
    def customer(self) -> DefaultCustomerType:
        return DefaultCustomerType(
            fullname=app_settings.DEFAULT_CUSTOMER_FULLNAME,
            shortcode=app_settings.DEFAULT_CUSTOMER_SHORTCODE,
            identifier=app_settings.DEFAULT_CUSTOMER_IDENTIFIER,
        )

    @strawberry.field(name="_metadataSchema", description="Returns metadata schema of a subscription")  # type: ignore
    def metadata_schema(self) -> dict:
        metadata_class = MetadataDict["metadata"]
        return metadata_class.schema() if metadata_class else static_metadata_schema

    @strawberry.field(description="Returns metadata of a subscription")  # type: ignore
    def metadata(self) -> dict:
        return get_subscription_metadata(str(self.subscription_id)) or {}


@strawberry.experimental.pydantic.type(model=SubscriptionModel, all_fields=True, directives=federation_key_directives)
class Subscription(SubscriptionInterface):
    pass

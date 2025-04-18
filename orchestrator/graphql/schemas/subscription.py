from datetime import datetime
from typing import Annotated
from uuid import UUID

import strawberry
from pydantic import BaseModel
from sqlalchemy import select
from strawberry import UNSET
from strawberry.federation.schema_directives import Key

from oauth2_lib.strawberry import authenticated_field
from orchestrator.db import FixedInputTable, ProductTable, SubscriptionTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.graphql.loaders.subscriptions import SubsLoaderType
from orchestrator.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.graphql.resolvers.process import resolve_processes
from orchestrator.graphql.schemas.customer import CustomerType
from orchestrator.graphql.schemas.customer_description import CustomerDescription
from orchestrator.graphql.schemas.helpers import get_original_model
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.schemas.product import ProductModelGraphql
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.get_subscription_product_blocks import (
    ProductBlockInstance,
    get_subscription_product_blocks,
)
from orchestrator.services.fixed_inputs import get_fixed_inputs
from orchestrator.services.subscription_relations import get_recursive_relations
from orchestrator.services.subscriptions import (
    get_subscription_metadata,
)
from orchestrator.settings import app_settings
from orchestrator.types import SubscriptionLifecycle

federation_key_directives = [Key(fields="subscriptionId", resolvable=UNSET)]

MetadataDict: dict[str, type[BaseModel] | None] = {"metadata": None}
static_metadata_schema = {"title": "SubscriptionMetadata", "type": "object", "properties": {}, "definitions": {}}


@strawberry.input(description="Filter recursion")
class SubscriptionRelationFilter:
    statuses: list[str] | None = strawberry.field(default=None, description="Search by statusses")
    recurse_depth_limit: int = strawberry.field(default=10, description="the limited depth to recurse through")
    recurse_product_types: list[str] | None = strawberry.field(
        default=None, description="List of product types to recurse into"
    )


async def _load_recursive_relations(
    subscription_id: UUID, relation_filter: SubscriptionRelationFilter | None, data_loader: SubsLoaderType
) -> list[SubscriptionTable]:
    sub_relation_filter = relation_filter or SubscriptionRelationFilter()

    async def get_subscriptions_from_loader(
        subscription_ids: list[UUID], filter_statuses: tuple[str, ...]
    ) -> list[list[SubscriptionTable]]:
        load_mapping = [(sub_id, filter_statuses) for sub_id in subscription_ids]
        return await data_loader.load_many(load_mapping)

    return await get_recursive_relations(
        [subscription_id],
        tuple(sub_relation_filter.statuses or ()),
        sub_relation_filter.recurse_product_types or [],
        sub_relation_filter.recurse_depth_limit,
        get_subscriptions_from_loader,
    )


@strawberry.federation.interface(description="Virtual base interface for subscriptions", keys=["subscriptionId"])
class SubscriptionInterface:
    subscription_id: UUID
    customer_id: str
    description: str
    start_date: datetime | None
    end_date: datetime | None
    status: SubscriptionLifecycle
    insync: bool
    note: str | None
    version: int

    @strawberry.field(description="Product information")  # type: ignore
    async def product(self) -> ProductModelGraphql:
        model = get_original_model(self, SubscriptionTable)

        return ProductModelGraphql.from_pydantic(model.product)

    @strawberry.field(name="_schema", description="Return all products block instances of a subscription as JSON Schema")  # type: ignore
    async def schema(self) -> dict:
        product_type_stmt = (
            select(ProductTable.name)
            .join(SubscriptionTable)
            .where(SubscriptionTable.subscription_id == self.subscription_id)
        )
        product_name = db.session.execute(product_type_stmt).scalar_one_or_none()
        if not product_name:
            return {}
        subscription_model = SUBSCRIPTION_MODEL_REGISTRY[product_name]
        subscription_base_model = subscription_model.__base_type__
        return subscription_base_model.model_json_schema() if subscription_base_model else {}

    @strawberry.field(description="Return all products block instances of a subscription")  # type: ignore
    async def product_block_instances(
        self, info: OrchestratorInfo, tags: list[str] | None = None, resource_types: list[str] | None = None
    ) -> list[ProductBlockInstance]:
        return await get_subscription_product_blocks(info, self.subscription_id, tags, resource_types)

    @strawberry.field(description="Return fixed inputs")  # type: ignore
    async def fixed_inputs(self) -> strawberry.scalars.JSON:
        model = get_original_model(self, SubscriptionTable)

        fixed_inputs = get_fixed_inputs(filters=[FixedInputTable.product_id == model.product.product_id])
        return [{"field": fi.name, "value": fi.value} for fi in fixed_inputs]

    @authenticated_field(description="Returns list of processes of the subscription")  # type: ignore
    async def processes(
        self,
        info: OrchestratorInfo,
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
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
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
        first: int = 10,
        after: int = 0,
        in_use_by_filter: SubscriptionRelationFilter | None = None,
    ) -> Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        subscriptions = await _load_recursive_relations(
            self.subscription_id, in_use_by_filter, info.context.core_in_use_by_subs_loader
        )

        subscription_ids = [str(subscription.subscription_id) for subscription in subscriptions]
        if not subscription_ids:
            return EMPTY_PAGE

        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionId", value="|".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)

    @authenticated_field(description="Returns list of subscriptions that this subscription depends on")  # type: ignore
    async def depends_on_subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
        first: int = 10,
        after: int = 0,
        depends_on_filter: SubscriptionRelationFilter | None = None,
    ) -> Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        subscriptions = await _load_recursive_relations(
            self.subscription_id, depends_on_filter, info.context.core_depends_on_subs_loader
        )

        subscription_ids = [str(subscription.subscription_id) for subscription in subscriptions]
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionId", value="|".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)

    @strawberry.field(description="Returns customer of a subscription")  # type: ignore
    def customer(self) -> CustomerType:
        return CustomerType(
            customer_id=app_settings.DEFAULT_CUSTOMER_IDENTIFIER,
            fullname=app_settings.DEFAULT_CUSTOMER_FULLNAME,
            shortcode=app_settings.DEFAULT_CUSTOMER_SHORTCODE,
        )

    @strawberry.field(description="Returns customer descriptions of a subscription")  # type: ignore
    def customer_descriptions(self) -> list[CustomerDescription]:
        db_model = self._original_model  # type: ignore
        if not isinstance(self._original_model, SubscriptionTable):  # type: ignore
            db_model = self._original_model._db_model  # type: ignore
        return [
            CustomerDescription.from_pydantic(customer_description)
            for customer_description in db_model.customer_descriptions
        ]

    @strawberry.field(name="_metadataSchema", description="Returns metadata schema of a subscription")  # type: ignore
    def metadata_schema(self) -> dict:
        metadata_class = MetadataDict["metadata"]
        return metadata_class.model_json_schema() if metadata_class else static_metadata_schema

    @strawberry.field(description="Returns metadata of a subscription")  # type: ignore
    def metadata(self) -> dict:
        return get_subscription_metadata(str(self.subscription_id)) or {}

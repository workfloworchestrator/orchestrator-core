from typing import TYPE_CHECKING, Annotated

import strawberry
from strawberry.federation.schema_directives import Key
from strawberry.scalars import JSON
from strawberry.unset import UNSET

from oauth2_lib.strawberry import authenticated_field
from orchestrator.db import ProductTable, db
from orchestrator.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.graphql.schemas.customer import CustomerType
from orchestrator.graphql.schemas.product import ProductType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.schemas.process import ProcessSchema, ProcessStepSchema
from orchestrator.settings import app_settings

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.subscription import SubscriptionInterface
else:
    SubscriptionInterface = Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]

federation_key_directives = [Key(fields="processId", resolvable=UNSET)]


@strawberry.experimental.pydantic.type(model=ProcessStepSchema)
class ProcessStepType:
    step_id: strawberry.auto
    name: strawberry.auto
    status: strawberry.auto
    created_by: strawberry.auto
    executed: strawberry.auto
    commit_hash: strawberry.auto
    state: JSON | None
    state_delta: JSON | None


@strawberry.experimental.pydantic.type(model=ProcessSchema, directives=federation_key_directives)
class ProcessType:
    process_id: strawberry.auto
    product_id: strawberry.auto
    customer_id: strawberry.auto
    workflow_id: strawberry.auto
    workflow_name: strawberry.auto
    workflow_target: strawberry.auto
    assignee: strawberry.auto
    failed_reason: strawberry.auto
    traceback: strawberry.auto
    last_step: strawberry.auto
    last_status: strawberry.auto
    created_by: strawberry.auto
    started_at: strawberry.auto
    last_modified_at: strawberry.auto
    is_task: strawberry.auto
    steps: strawberry.auto
    form: JSON | None
    current_state: JSON | None

    @authenticated_field(description="Returns the associated product")  # type: ignore
    def product(self) -> ProductType | None:
        if self.product_id and (product := db.session.get(ProductTable, self.product_id)):
            return ProductType.from_pydantic(product)
        return None

    @strawberry.field(description="Returns customer of a subscription")  # type: ignore
    def customer(self) -> CustomerType:
        return CustomerType(
            customer_id=app_settings.DEFAULT_CUSTOMER_IDENTIFIER,
            fullname=app_settings.DEFAULT_CUSTOMER_FULLNAME,
            shortcode=app_settings.DEFAULT_CUSTOMER_SHORTCODE,
        )

    @authenticated_field(description="Returns list of subscriptions of the process")  # type: ignore
    async def subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[SubscriptionInterface]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        subscription_ids = [str(s.subscription_id) for s in self._original_model.subscriptions]  # type: ignore
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionId", value="|".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)

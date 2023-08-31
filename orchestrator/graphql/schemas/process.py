from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Optional, Union
from uuid import UUID

import strawberry
from more_itertools import first
from strawberry.federation.schema_directives import Key
from strawberry.scalars import JSON
from strawberry.unset import UNSET

from oauth2_lib.strawberry import authenticated_field
from orchestrator.db.models import ProductTable
from orchestrator.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.graphql.schemas.product import ProductType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.schemas.process import ProcessForm, ProcessSchema, ProcessStepSchema
from orchestrator.workflow import ProcessStatus

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.subscription import SubscriptionInterface


federation_key_directives = [Key(fields="id", resolvable=UNSET)]


@strawberry.experimental.pydantic.type(model=ProcessForm)
class ProcessFormType:
    title: strawberry.auto
    type: strawberry.auto
    additionalProperties: strawberry.auto
    required: strawberry.auto
    properties: JSON
    definitions: Union[JSON, None]


@strawberry.experimental.pydantic.type(model=ProcessStepSchema)
class ProcessStepType:
    step_id: strawberry.auto
    name: strawberry.auto
    status: strawberry.auto
    created_by: strawberry.auto
    executed: strawberry.auto
    commit_hash: strawberry.auto
    state: Union[JSON, None]


@strawberry.experimental.pydantic.type(model=ProcessSchema, directives=federation_key_directives)
class ProcessType:
    process_id: strawberry.auto
    product_id: strawberry.auto
    customer_id: strawberry.auto
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
    form: strawberry.auto
    current_state: Union[JSON, None]

    @authenticated_field(
        description="Returns process id",
        deprecation_reason="Changed to 'process_id' from version 1.2.3, removing after version 1.3.0",
    )  # type: ignore
    def pid(self) -> UUID:
        return self.process_id

    @authenticated_field(
        description="Returns process workflow name",
        deprecation_reason="Changed to 'workflow_name' from version 1.2.3, removing after version 1.3.0",
    )  # type: ignore
    def workflow(self) -> str:
        return self.workflow

    @authenticated_field(
        description="Returns process last status",
        deprecation_reason="Changed to 'last_status' from version 1.2.3, removing after version 1.3.0",
    )  # type: ignore
    def status(self) -> ProcessStatus:
        return self.last_status

    @authenticated_field(
        description="Returns process id",
        deprecation_reason="Changed to 'last_step' from version 1.2.3, removing after version 1.3.0",
    )  # type: ignore
    def step(self) -> str:
        return self.last_step

    @authenticated_field(
        description="Returns process started at datetime",
        deprecation_reason="Changed to 'started_at' from version 1.2.3, removing after version 1.3.0",
    )  # type: ignore
    def started(self) -> datetime:
        return self.started_at

    @authenticated_field(
        description="Returns process last modified at datetime",
        deprecation_reason="Changed to 'last_modified_at' from version 1.2.3, removing after version 1.3.0",
    )  # type: ignore
    def last_modified(self) -> datetime:
        return self.last_modified_at

    @authenticated_field(description="Returns the associated product")  # type: ignore
    def product(self) -> Optional[ProductType]:
        subscription = first(self._original_model.subscriptions, None)  # type: ignore
        product = None
        if subscription:
            product = ProductTable.query.get(subscription.product_id)
        return product

    @authenticated_field(description="Returns list of subscriptions of the process")  # type: ignore
    async def subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        subscription_ids = [str(s.subscription_id) for s in self._original_model.subscriptions]  # type: ignore
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionIds", value=",".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)

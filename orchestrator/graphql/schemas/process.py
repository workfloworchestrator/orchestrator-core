from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional, Union
from uuid import UUID

import strawberry
from oauth2_lib.graphql_authentication import authenticated_field
from sqlalchemy.orm import load_only
from strawberry.scalars import JSON

from orchestrator.config.assignee import Assignee
from orchestrator.db import ProcessTable
from orchestrator.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.process import ProcessForm, ProcessStepSchema
from orchestrator.workflow import ProcessStatus

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.subscription import SubscriptionType


# TODO: Change to the orchestrator.schemas.process version when subscriptions are typed in strawberry.
class ProcessBaseSchema(OrchestratorBaseModel):
    id: UUID
    workflow_name: str
    product: Optional[UUID]
    customer: Optional[UUID]
    assignee: Assignee
    failed_reason: Optional[str]
    traceback: Optional[str]
    step: Optional[str]
    status: ProcessStatus
    last_step: Optional[str]
    created_by: Optional[str]
    started: datetime
    last_modified: datetime
    is_task: bool


class ProcessGraphqlSchema(ProcessBaseSchema):
    current_state: Dict[str, Any]
    steps: List[ProcessStepSchema]
    form: Optional[ProcessForm]


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
    stepid: strawberry.auto
    name: strawberry.auto
    status: strawberry.auto
    created_by: strawberry.auto
    executed: strawberry.auto
    commit_hash: strawberry.auto
    state: Union[JSON, None]


@strawberry.experimental.pydantic.type(model=ProcessGraphqlSchema)
class ProcessType:
    id: strawberry.auto
    workflow_name: strawberry.auto
    product: strawberry.auto
    customer: strawberry.auto
    assignee: strawberry.auto
    failed_reason: strawberry.auto
    traceback: strawberry.auto
    step: strawberry.auto
    status: strawberry.auto
    last_step: strawberry.auto
    created_by: strawberry.auto
    started: strawberry.auto
    last_modified: strawberry.auto
    is_task: strawberry.auto
    steps: strawberry.auto
    form: strawberry.auto
    current_state: Union[JSON, None]

    @authenticated_field(description="Returns list of subscriptions of the process")  # type: ignore
    async def subscriptions(
        self,
        info: CustomInfo,
        filter_by: Union[list[GraphqlFilter], None] = None,
        sort_by: Union[list[GraphqlSort], None] = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[Annotated["SubscriptionType", strawberry.lazy(".subscription")]]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        process: ProcessTable = ProcessTable.query.options(load_only(ProcessTable.process_subscriptions)).get(self.id)
        subscription_ids = [str(s.subscription_id) for s in process.process_subscriptions]
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionIds", value=",".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)

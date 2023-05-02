from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import strawberry
from strawberry.scalars import JSON

from orchestrator.config.assignee import Assignee
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.process import ProcessForm, ProcessStepSchema
from orchestrator.workflow import ProcessStatus


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
    # subscriptions: List[SubscriptionBaseSchema]
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

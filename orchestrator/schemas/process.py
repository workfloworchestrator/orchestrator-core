# Copyright 2019-2020 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID

from pydantic import ConfigDict, Field, model_serializer
from pydantic_core.core_schema import SerializerFunctionWrapHandler, ValidationInfo

from orchestrator.config.assignee import Assignee
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.subscription import SubscriptionSchema
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus


class ProcessIdSchema(OrchestratorBaseModel):
    id: UUID


class ProcessForm(OrchestratorBaseModel):
    title: str
    type: str
    properties: Dict[str, Any]
    additionalProperties: bool  # noqa: N815
    required: List[str] = []
    definitions: Optional[Dict[str, Any]] = Field(None, validation_alias="$defs")

    @model_serializer(mode="wrap", when_used="json")
    def serialize_defs(self, handler: SerializerFunctionWrapHandler, _info: ValidationInfo) -> dict[str, Any]:
        """Serialize ProcessForm model.

        Pydantic 2.x renamed 'definitions' to '$defs' to be compliant with JSONSchema.
        Python doesn't allow variables starting with $ so we keep the field name 'definitions', we set a
        validation_alias '$defs' for the input, and in the json output this serializer renames it to '$defs'.
        """
        serialized = handler(self)
        serialized["$defs"] = serialized.pop("definitions")
        return serialized


class ProcessBaseSchema(OrchestratorBaseModel):
    process_id: UUID
    workflow_name: str
    is_task: bool
    created_by: Optional[str] = None
    failed_reason: Optional[str] = None
    started_at: datetime
    last_status: ProcessStatus
    last_step: Optional[str] = None
    assignee: Assignee
    last_modified_at: datetime
    traceback: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ProcessStepSchema(OrchestratorBaseModel):
    step_id: Optional[UUID] = None
    name: str
    status: str
    created_by: Optional[str] = None
    executed: Optional[datetime] = None
    commit_hash: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    state_delta: Optional[Dict[str, Any]] = None

    stepid: Optional[UUID] = None  # TODO: will be removed in 1.4


class ProcessSchema(ProcessBaseSchema):
    product_id: Optional[UUID] = None
    customer_id: Optional[str] = None
    workflow_target: Optional[Target] = None
    subscriptions: List[SubscriptionSchema]
    current_state: Optional[Dict[str, Any]] = None
    steps: Optional[List[ProcessStepSchema]] = None
    form: Optional[ProcessForm] = None


class ProcessDeprecationsSchema(ProcessSchema):
    id: Optional[UUID] = None  # TODO: will be removed in 1.4
    pid: Optional[UUID] = None  # TODO: will be removed in 1.4
    workflow: Optional[str] = None  # TODO: will be removed in 1.4
    status: Optional[ProcessStatus] = None  # TODO: will be removed in 1.4
    step: Optional[str] = None  # TODO: will be removed in 1.4
    started: Optional[datetime] = None  # TODO: will be removed in 1.4
    last_modified: Optional[datetime] = None  # TODO: will be removed in 1.4
    product: Optional[UUID] = None  # TODO: will be removed in 1.4
    customer: Optional[str] = None  # TODO: will be removed in 1.4


class ProcessSubscriptionBaseSchema(OrchestratorBaseModel):
    id: UUID
    process_id: UUID
    subscription_id: UUID
    workflow_target: Optional[Target] = None
    created_at: datetime

    pid: UUID  # TODO: will be removed in 1.4
    model_config = ConfigDict(from_attributes=True)


class ProcessSubscriptionSchema(ProcessSubscriptionBaseSchema):
    process: ProcessBaseSchema


class ProcessResumeAllSchema(OrchestratorBaseModel):
    count: int


class ProcessStatusCounts(OrchestratorBaseModel):
    process_counts: Dict[ProcessStatus, int]
    task_counts: Dict[ProcessStatus, int]


Reporter = Annotated[str, Field(max_length=100)]

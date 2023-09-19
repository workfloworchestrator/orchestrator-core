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
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import ConstrainedStr

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
    definitions: Optional[Dict[str, Any]]


class ProcessBaseSchema(OrchestratorBaseModel):
    process_id: UUID
    workflow_name: str
    is_task: bool
    created_by: Optional[str]
    failed_reason: Optional[str]
    started_at: datetime
    last_status: ProcessStatus
    last_step: Optional[str]
    assignee: Assignee
    last_modified_at: datetime
    traceback: Optional[str]

    class Config:
        orm_mode = True


class ProcessStepSchema(OrchestratorBaseModel):
    step_id: Optional[UUID]
    name: str
    status: str
    created_by: Optional[str] = None
    executed: Optional[datetime]
    commit_hash: Optional[str] = None
    state: Optional[Dict[str, Any]]

    stepid: Optional[UUID]  # TODO: will be removed in 1.4


class ProcessSchema(ProcessBaseSchema):
    product_id: Optional[UUID]
    customer_id: Optional[str]
    workflow_target: Optional[Target]
    subscriptions: List[SubscriptionSchema]
    current_state: Optional[Dict[str, Any]]
    steps: Optional[List[ProcessStepSchema]]
    form: Optional[ProcessForm]


class ProcessDeprecationsSchema(ProcessSchema):
    id: Optional[UUID]  # TODO: will be removed in 1.4
    pid: Optional[UUID]  # TODO: will be removed in 1.4
    workflow: Optional[str]  # TODO: will be removed in 1.4
    status: Optional[ProcessStatus]  # TODO: will be removed in 1.4
    step: Optional[str]  # TODO: will be removed in 1.4
    started: Optional[datetime]  # TODO: will be removed in 1.4
    last_modified: Optional[datetime]  # TODO: will be removed in 1.4
    product: Optional[UUID]  # TODO: will be removed in 1.4
    customer: Optional[str]  # TODO: will be removed in 1.4


class ProcessSubscriptionBaseSchema(OrchestratorBaseModel):
    id: UUID
    process_id: UUID
    subscription_id: UUID
    workflow_target: Optional[Target]
    created_at: datetime

    pid: UUID  # TODO: will be removed in 1.4

    class Config:
        orm_mode = True


class ProcessSubscriptionSchema(ProcessSubscriptionBaseSchema):
    process: ProcessBaseSchema


class ProcessResumeAllSchema(OrchestratorBaseModel):
    count: int


class ProcessStatusCounts(OrchestratorBaseModel):
    process_counts: Dict[ProcessStatus, int]
    task_counts: Dict[ProcessStatus, int]


class Reporter(ConstrainedStr):
    max_length = 100

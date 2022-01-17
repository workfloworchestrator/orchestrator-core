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

from orchestrator.config.assignee import Assignee
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.subscription import SubscriptionBaseSchema
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus


class ProcessIdSchema(OrchestratorBaseModel):
    id: UUID


class ProcessForm(OrchestratorBaseModel):
    title: str
    type: str
    properties: Dict[str, Any]
    additionalProperties: bool
    required: List[str] = []
    definitions: Optional[Dict[str, Any]]


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
    subscriptions: List[SubscriptionBaseSchema]
    is_task: bool


class ProcessStepSchema(OrchestratorBaseModel):
    stepid: Optional[UUID]
    name: str
    status: str
    created_by: Optional[str] = None
    executed: Optional[datetime]
    commit_hash: Optional[str] = None
    state: Optional[Dict[str, Any]]


class ProcessSchema(ProcessBaseSchema):
    current_state: Dict[str, Any]
    steps: List[ProcessStepSchema]
    form: Optional[ProcessForm]


class ProcessSubscriptionProcessSchema(OrchestratorBaseModel):
    workflow: str
    pid: UUID
    is_task: bool
    created_by: Optional[str]
    failed_reason: Optional[str]
    started_at: datetime
    last_status: ProcessStatus
    assignee: Assignee
    last_modified_at: datetime
    traceback: Optional[str]
    last_step: Optional[str]

    class Config:
        orm_mode = True


class ProcessSubscriptionBaseSchema(OrchestratorBaseModel):
    workflow_target: Optional[Target]
    subscription_id: UUID
    id: UUID
    pid: UUID
    created_at: datetime

    class Config:
        orm_mode = True


class ProcessSubscriptionSchema(ProcessSubscriptionBaseSchema):
    process: ProcessSubscriptionProcessSchema


class ProcessListItemSchema(OrchestratorBaseModel):
    assignee: Assignee
    created_by: Optional[str]
    failed_reason: Optional[str]
    last_modified_at: datetime
    pid: UUID
    started_at: datetime
    last_status: ProcessStatus
    last_step: Optional[str]
    workflow: str
    workflow_target: Optional[Target]
    is_task: bool
    subscriptions: List[SubscriptionBaseSchema]

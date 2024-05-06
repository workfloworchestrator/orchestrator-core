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
from typing import Annotated, Any
from uuid import UUID

from pydantic import ConfigDict, Field

from orchestrator.config.assignee import Assignee
from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.subscription import SubscriptionSchema
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus


class ProcessIdSchema(OrchestratorBaseModel):
    id: UUID


class ProcessBaseSchema(OrchestratorBaseModel):
    process_id: UUID
    workflow_id: UUID
    workflow_name: str
    is_task: bool
    created_by: str | None = None
    failed_reason: str | None = None
    started_at: datetime
    last_status: ProcessStatus
    last_step: str | None = None
    assignee: Assignee
    last_modified_at: datetime
    traceback: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ProcessStepSchema(OrchestratorBaseModel):
    step_id: UUID | None = None
    name: str
    status: str
    created_by: str | None = None
    executed: datetime | None = None
    commit_hash: str | None = None
    state: dict[str, Any] | None = None
    state_delta: dict[str, Any] | None = None


class ProcessSchema(ProcessBaseSchema):
    product_id: UUID | None = None
    customer_id: str | None = None
    workflow_target: Target | None = None
    subscriptions: list[SubscriptionSchema]
    current_state: dict[str, Any] | None = None
    steps: list[ProcessStepSchema] | None = None
    form: dict[str, Any] | None = None


class ProcessResumeAllSchema(OrchestratorBaseModel):
    count: int


class ProcessStatusCounts(OrchestratorBaseModel):
    process_counts: dict[ProcessStatus, int]
    task_counts: dict[ProcessStatus, int]


Reporter = Annotated[str, Field(max_length=100)]

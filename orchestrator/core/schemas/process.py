# Copyright 2019-2026 SURF, ESnet, GÉANT.
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
from enum import StrEnum
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db.models import NOTE_LENGTH
from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.schemas.subscription import SubscriptionSchema
from orchestrator.core.targets import Target
from orchestrator.core.workflow import ProcessStatus, StepImportance


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
    executed: datetime | None = Field(
        None, deprecated="Deprecated, use 'started' and 'completed' for step start and completion times"
    )
    started: datetime | None = None
    completed: datetime | None = None
    commit_hash: str | None = None
    importance: StepImportance = StepImportance.DEFAULT
    state: dict[str, Any] | None = None
    state_delta: dict[str, Any] | None = None
    parallel_total_branches: int | None = None  # TODO add Field description
    parallel_completed_count: int | None = None  # TODO add Field description
    child_steps: list["ProcessStepSchema"] | None = None


class ProcessSchema(ProcessBaseSchema):
    product_id: UUID | None = None
    customer_id: str | None = None
    workflow_target: Target | None = None
    subscriptions: list[SubscriptionSchema]
    current_state: dict[str, Any] | None = None
    steps: list[ProcessStepSchema] | None = None
    form: dict[str, Any] | None = None
    note: str | None = None


class ProcessResumeAllSchema(OrchestratorBaseModel):
    count: int


class ProcessStatusCounts(OrchestratorBaseModel):
    process_counts: dict[ProcessStatus, int]
    task_counts: dict[ProcessStatus, int]


class ProcessPatchSchema(OrchestratorBaseModel):
    note: Annotated[str, Field(max_length=NOTE_LENGTH)] | None = None


class ProcessBulkAction(StrEnum):
    RESUME = "resume"
    ABORT = "abort"
    DELETE = "delete"
    NOTE = "note"


class ProcessBulkSchema(OrchestratorBaseModel):
    action: ProcessBulkAction
    # Bounds the single IN query and the sequential per-process resume/abort within one request
    process_ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]
    note: Annotated[str, Field(max_length=NOTE_LENGTH)] | None = None

    @model_validator(mode="after")
    def note_given_for_note_action(self) -> Self:
        # `None` clears the note, so only an omitted field is an error
        if self.action == ProcessBulkAction.NOTE and "note" not in self.model_fields_set:
            raise ValueError("'note' is required for the 'note' action")
        return self


class ProcessBulkItemResult(OrchestratorBaseModel):
    process_id: UUID
    success: bool
    error: str | None = None


class ProcessBulkResultSchema(OrchestratorBaseModel):
    action: ProcessBulkAction
    count: int
    results: list[ProcessBulkItemResult]


Reporter = Annotated[str, Field(max_length=100)]

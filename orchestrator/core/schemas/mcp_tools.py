# Copyright 2019-2026 SURF, GÉANT.
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
from typing import Any
from uuid import UUID

from pydantic import Field

from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.types import SubscriptionLifecycle
from orchestrator.core.workflow import ProcessStatus

# Request models


class ListWorkflowsRequest(OrchestratorBaseModel):
    target: str | None = Field(
        default=None,
        description='Filter by workflow target. Valid values: "create", "modify", "terminate", "system", "validate", "reconcile". Leave empty for all.',
    )
    is_task: bool | None = Field(
        default=None,
        description="Filter by whether the workflow is a background task (True) or user-facing (False). Leave empty for all.",
    )


class GetWorkflowFormRequest(OrchestratorBaseModel):
    workflow_key: str = Field(description='Workflow name in snake_case (e.g. "create_node", "modify_note").')
    page_inputs: list[dict[str, Any]] | None = Field(
        default=None,
        description="List of dicts with previously filled form pages. Pass `[]` or omit for the first page.",
    )


class SubscriptionIdRequest(OrchestratorBaseModel):
    subscription_id: str = Field(description="UUID of the subscription.")


class ProcessIdRequest(OrchestratorBaseModel):
    process_id: str = Field(description="UUID of the process.")


class ListRecentProcessesRequest(OrchestratorBaseModel):
    status: str | None = Field(
        default=None,
        description='Filter by process status (e.g. "running", "suspended", "failed"). Leave empty for all.',
    )
    workflow_name: str | None = Field(default=None, description='Filter by workflow name (e.g. "modify_note").')
    is_task: bool | None = Field(
        default=None, description="Filter to background tasks (True) or user workflows (False)."
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of processes to return.")


# Response models


class WorkflowFormPage(OrchestratorBaseModel):
    page: int = Field(description="Current page number (0-indexed).")
    complete: bool = Field(description="True when all pages have been filled and `create_workflow` may be called.")
    schema_: dict[str, Any] | None = Field(
        default=None,
        alias="schema",
        description="JSON Schema for the current page's fields. `null` when complete.",
    )


class ProcessSummary(OrchestratorBaseModel):
    process_id: UUID
    workflow_name: str | None = None
    last_status: ProcessStatus
    last_step: str | None = None
    started_at: datetime | None = None
    last_modified_at: datetime | None = None
    created_by: str | None = None
    is_task: bool


class ProcessStatusResponse(ProcessSummary):
    failed_reason: str | None = None
    traceback: str | None = None
    form: dict[str, Any] | None = None
    current_state: dict[str, Any] | None = None


class ProductSummary(OrchestratorBaseModel):
    product_id: UUID
    name: str
    product_type: str
    tag: str | None = None
    description: str | None = None


class SubscriptionDetailsResponse(OrchestratorBaseModel):
    subscription_id: UUID
    description: str | None = None
    status: SubscriptionLifecycle
    insync: bool
    product: ProductSummary
    customer_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    note: str | None = None

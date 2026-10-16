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
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.types import SubscriptionLifecycle
from orchestrator.core.workflow import ProcessStatus
from pydantic_forms.core import FormFieldError  # used here, and re-exported: the 5.5.0 import path

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
    verdict: Literal["error", "result"] = Field(
        default="error",
        description=(
            'How a page the form rejects is reported. "error" (default): the validation errors are raised as a tool '
            'error. "result": the page comes back with `status: "rejected"`, its `errors` and its `schema`, so the '
            "values named can be corrected and the same page resubmitted."
        ),
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


class ListSubscriptionsRequest(OrchestratorBaseModel):
    limit: int = Field(default=10, ge=1, le=20, description="Maximum number of subscriptions to return.")


# Response models


class WorkflowFormPage(OrchestratorBaseModel):
    page: int = Field(description="The page this result is about (0-indexed).")
    complete: bool = Field(description="True when all pages have been filled and `create_workflow` may be called.")
    status: Literal["next", "complete", "rejected"] = Field(
        description='"next": fill `schema` and call again with the page added to `page_inputs`. "complete": call '
        '`create_workflow`. "rejected": page `page` did not validate; fix the values `errors` name and resubmit it.'
    )
    title: str | None = Field(default=None, description="The page's title, when the form gives it one.")
    schema_: dict[str, Any] | None = Field(
        default=None,
        alias="schema",
        description="The page as one self-contained JSON Schema: the values to submit, every reference inlined. "
        "A property with `readOnly: true` is shown and takes no value; `enum` lists the values a property takes "
        'and `options` their labels; `format: "accept"` takes `"ACCEPTED"`. `null` when complete.',
    )
    errors: list[FormFieldError] = Field(
        default_factory=list, description='The verdict on a rejected page; empty unless `status` is "rejected".'
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


class SubscriptionSummary(OrchestratorBaseModel):
    subscription_id: UUID
    description: str | None = None
    status: SubscriptionLifecycle
    insync: bool
    product_name: str
    customer_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class ListSubscriptionsResponse(OrchestratorBaseModel):
    subscriptions: list[SubscriptionSummary]
    has_more: bool = Field(description="True when more subscriptions exist beyond the returned limit.")


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

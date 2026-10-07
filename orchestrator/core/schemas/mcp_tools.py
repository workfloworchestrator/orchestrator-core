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
    include_schema: bool = Field(
        default=True,
        description="Also send the page's browser JSON Schema as `schema` (deprecated: read `fields`). Pass false "
        "to receive `fields` only.",
    )
    verdict: Literal["error", "result"] = Field(
        default="error",
        description=(
            'How a page the form rejects is reported. "error" (default): the validation errors are raised as a tool '
            'error. "result": the page comes back with `status: "rejected"`, its `errors` and its `fields`, so the '
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


FormFieldKind = Literal["string", "integer", "number", "boolean", "list", "object", "any"]


class FormFieldOption(OrchestratorBaseModel):
    value: Any = Field(description="What a caller submits for this option.")
    label: str = Field(description="How a person sees the option (a product's name, a Choice label).")


class FormFieldError(OrchestratorBaseModel):
    loc: list[int | str] = Field(
        description='Path of the rejected value on the page: the field name, then an index or sub-field. `["__root__"]` for a page-level error.'
    )
    msg: str = Field(description="The message, as the UI shows it.")
    type: str = Field(description='pydantic\'s error type, e.g. "missing", "enum", "value_error".')


class FormField(OrchestratorBaseModel):
    """One field of a form page, as data: what it takes, what it is limited to, and whether it is asked at all."""

    name: str
    title: str
    description: str | None = None
    kind: FormFieldKind = Field(description="The kind of value the field takes.")
    format: str | None = Field(
        default=None,
        description='The form\'s marker for a special field, e.g. "accept", "productId", "customerId", "subscription", "summary".',
    )
    required: bool
    default: Any = Field(default=None, description="The value that applies when none is sent (`null` when required).")
    nullable: bool = False
    options: list[FormFieldOption] | None = Field(
        default=None,
        description="The values the field is limited to, in order. `[]`: a choice with no option today. `null`: free.",
    )
    item: "FormField | None" = Field(default=None, description='For kind "list": the shape of one item.')
    min_items: int | None = None
    max_items: int | None = None
    unique_items: bool = False
    fields: "list[FormField] | None" = Field(
        default=None, description='For kind "object": the nested fields, in order.'
    )
    read_only: bool = Field(default=False, description="Shown with its `default` and never asked; do not submit.")
    display_only: bool = Field(
        default=False, description="A label, divider, text or summary table: shown and never submitted."
    )
    data: Any = Field(default=None, description="What a display field shows: a summary table, a text, accept items.")


class WorkflowFormPage(OrchestratorBaseModel):
    page: int = Field(description="The page this result is about (0-indexed).")
    complete: bool = Field(description="True when all pages have been filled and `create_workflow` may be called.")
    status: Literal["next", "complete", "rejected"] = Field(
        description='"next": fill `fields` and call again with the page added to `page_inputs`. "complete": call '
        '`create_workflow`. "rejected": page `page` did not validate; fix the values `errors` name and resubmit it.'
    )
    title: str | None = Field(default=None, description="The page's title, when the form gives it one.")
    schema_: dict[str, Any] | None = Field(
        default=None,
        alias="schema",
        deprecated="`schema` is the browser's rendering of the page; read `fields`. It is removed in the next major release.",
        description="Deprecated, read `fields` instead: the browser's JSON Schema of the page. `null` when complete "
        "or when `include_schema` is false; to be removed in the next major release.",
    )
    fields: list[FormField] | None = Field(
        default=None, description="The page's fields as data, in the form's order. `null` when complete."
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

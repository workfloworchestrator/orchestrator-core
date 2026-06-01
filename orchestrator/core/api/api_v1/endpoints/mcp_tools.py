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

"""REST endpoints designed as LLM tools.

These routes exist alongside the standard REST API (`/api/processes`,
`/api/subscriptions`, etc.) but are created specifically for LLM agent
consumption.

Every route is tagged ``AgentTag.EXPOSED`` so ``orchestrator.core.mcp.server``
auto-generates them as MCP tools alongside the action endpoints in
``processes.py`` and ``products.py``. The route ``operation_id`` becomes the
MCP tool name.

Why these are curated rather than auto-generated from the existing REST API:

* ``list_workflows`` —> no list route exists on ``/workflows`` (only
  ``/{id}`` and PATCH).
* ``get_workflow_form`` —> multi-page form pagination has stateful semantics
  (page N's schema depends on inputs from pages 0..N-1) that don't map to a
  single REST resource.
* ``get_subscription_available_workflows`` —> the equivalent REST route
  (``/subscriptions/workflows/{id}``) is deprecated and returns a richer
  schema.
* ``get_process_status`` —> REST ``GET /processes/{id}`` returns the full
  enriched payload including step history; this curated subset keeps the
  LLM context budget reasonable.
* ``list_recent_processes`` —> REST ``GET /processes/?filter=k,v,k,v`` uses
  a flat positional filter syntax that LLMs handle poorly; this exposes
  named kwargs.
* ``get_subscription_details`` —> REST ``GET /subscriptions/domain-model/{id}``
  returns the full product-block tree; this returns a flat header.
* ``search_subscriptions`` —> REST ``GET /subscriptions/search?query=`` only
  supports free-text; this adds typed ``status`` and ``product_type``
  filters.
"""

from http import HTTPStatus
from typing import Any
from uuid import UUID

import structlog
from fastapi.routing import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from orchestrator.core.agent_tags import AgentTag
from orchestrator.core.api.error_handling import raise_status
from orchestrator.core.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable, db
from orchestrator.core.schemas.mcp_tools import (
    GetWorkflowFormRequest,
    ListRecentProcessesRequest,
    ListWorkflowsRequest,
    ProcessIdRequest,
    ProcessStatusResponse,
    ProcessSummary,
    ProductSummary,
    SearchSubscriptionsRequest,
    SubscriptionDetailsResponse,
    SubscriptionIdRequest,
    SubscriptionSearchResult,
    WorkflowFormPage,
)
from orchestrator.core.schemas.workflow import SubscriptionWorkflowListsSchema, WorkflowSchema
from orchestrator.core.services.processes import _get_process, load_process
from orchestrator.core.services.subscriptions import get_subscription, subscription_workflows
from orchestrator.core.services.workflows import get_workflows
from orchestrator.core.utils.enrich_process import enrich_process
from orchestrator.core.workflows import get_workflow

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/list_workflows",
    response_model=list[WorkflowSchema],
    tags=[AgentTag.EXPOSED, AgentTag.LARGE, AgentTag.READONLY],
    operation_id="list_workflows",
)
def list_workflows_endpoint(params: ListWorkflowsRequest) -> list[WorkflowSchema]:
    """List all registered workflows in the orchestrator.

    Use this to discover what workflows are available before starting one.
    """
    filters: dict[str, Any] = {}
    if params.target is not None:
        filters["target"] = params.target.upper()
    if params.is_task is not None:
        filters["is_task"] = params.is_task
    return list(get_workflows(filters=filters or None, include_steps=False))


@router.post(
    "/get_workflow_form",
    response_model=WorkflowFormPage,
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="get_workflow_form",
)
def get_workflow_form_endpoint(params: GetWorkflowFormRequest) -> WorkflowFormPage:
    """Get the JSON Schema of a workflow's form page by page.

    IMPORTANT: Workflow forms are multi-page. You MUST call this tool repeatedly,
    adding each filled page to ``page_inputs``, until ``complete=true``. Only
    then call ``create_workflow`` with all accumulated ``page_inputs``.

    Algorithm:
        1. Call ``get_workflow_form(workflow_key)`` to get page 0 schema.
        2. Fill in the fields shown in the schema.
        3. Call ``get_workflow_form(workflow_key, [page0_data])`` to get page 1.
        4. Repeat until ``complete=true``.
        5. Call ``create_workflow(workflow_key, [page0_data, page1_data, ...])``.
    """
    # Lazy-import to avoid a circular import
    from orchestrator.core.forms import generate_form

    wf = get_workflow(params.workflow_key)
    if not wf:
        raise_status(HTTPStatus.NOT_FOUND, f"Workflow '{params.workflow_key}' does not exist")
    initial_state: dict[str, Any] = {"workflow_name": params.workflow_key, "workflow_target": wf.target}
    user_inputs = params.page_inputs or []
    page_index = len(user_inputs)
    form_schema = generate_form(wf.initial_input_form, initial_state, user_inputs)
    return WorkflowFormPage(page=page_index, complete=form_schema is None, schema=form_schema)


@router.post(
    "/get_subscription_available_workflows",
    response_model=SubscriptionWorkflowListsSchema,
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="get_subscription_available_workflows",
)
def get_subscription_available_workflows_endpoint(params: SubscriptionIdRequest) -> SubscriptionWorkflowListsSchema:
    """Get workflows available for a specific subscription.

    Shows which workflows can be run on this subscription and why some may be
    blocked (e.g. subscription not in sync, wrong lifecycle state). Workflows
    are grouped by target (create, modify, terminate, etc.); blocked entries
    carry a ``reason`` field.
    """
    try:
        subscription = get_subscription(UUID(params.subscription_id))
    except ValueError as exc:
        raise_status(HTTPStatus.NOT_FOUND, f"Subscription not found: {exc}")
    return SubscriptionWorkflowListsSchema.model_validate(subscription_workflows(subscription))


@router.post(
    "/get_process_status",
    response_model=ProcessStatusResponse,
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="get_process_status",
)
def get_process_status_endpoint(params: ProcessIdRequest) -> ProcessStatusResponse:
    """Get the current status and details of a workflow process.

    If the process is SUSPENDED, the response includes the form schema for the
    input needed to resume it.
    """
    process = _get_process(UUID(params.process_id))
    pstat = load_process(process)
    enriched = enrich_process(process, pstat)
    return ProcessStatusResponse(
        process_id=process.process_id,
        workflow_name=process.workflow.name if process.workflow else None,
        last_status=process.last_status,
        last_step=process.last_step,
        started_at=process.started_at,
        last_modified_at=process.last_modified_at,
        created_by=process.created_by,
        is_task=process.is_task,
        failed_reason=process.failed_reason,
        traceback=process.traceback,
        form=enriched.get("form"),
        current_state=enriched.get("current_state"),
    )


@router.post(
    "/list_recent_processes",
    response_model=list[ProcessSummary],
    tags=[AgentTag.EXPOSED, AgentTag.LARGE, AgentTag.READONLY],
    operation_id="list_recent_processes",
)
def list_recent_processes_endpoint(params: ListRecentProcessesRequest) -> list[ProcessSummary]:
    """List recent workflow processes, optionally filtered by status or workflow."""
    stmt = (
        select(ProcessTable)
        .options(joinedload(ProcessTable.workflow))
        .order_by(ProcessTable.started_at.desc())
        .limit(params.limit)
    )
    if params.status is not None:
        stmt = stmt.where(ProcessTable.last_status == params.status)
    if params.is_task is not None:
        stmt = stmt.where(ProcessTable.is_task.is_(params.is_task))
    if params.workflow_name is not None:
        stmt = stmt.join(WorkflowTable).where(WorkflowTable.name == params.workflow_name)

    processes = db.session.scalars(stmt).unique().all()
    return [
        ProcessSummary(
            process_id=p.process_id,
            workflow_name=p.workflow.name if p.workflow else None,
            last_status=p.last_status,
            last_step=p.last_step,
            started_at=p.started_at,
            last_modified_at=p.last_modified_at,
            created_by=p.created_by,
            is_task=p.is_task,
        )
        for p in processes
    ]


@router.post(
    "/get_subscription_details",
    response_model=SubscriptionDetailsResponse,
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="get_subscription_details",
)
def get_subscription_details_endpoint(params: SubscriptionIdRequest) -> SubscriptionDetailsResponse:
    """Get summary information about a subscription.

    Returns a flat header (status, product, customer, dates), no nested
    product blocks or in-use-by relations.
    """
    try:
        subscription = get_subscription(UUID(params.subscription_id))
    except ValueError as exc:
        raise_status(HTTPStatus.NOT_FOUND, f"Subscription not found: {exc}")
    return SubscriptionDetailsResponse(
        subscription_id=subscription.subscription_id,
        description=subscription.description,
        status=subscription.status,
        insync=subscription.insync,
        product=ProductSummary(
            product_id=subscription.product.product_id,
            name=subscription.product.name,
            product_type=subscription.product.product_type,
            tag=subscription.product.tag,
            description=subscription.product.description,
        ),
        customer_id=subscription.customer_id,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        note=subscription.note,
    )


@router.post(
    "/search_subscriptions",
    response_model=list[SubscriptionSearchResult],
    tags=[AgentTag.EXPOSED, AgentTag.LARGE, AgentTag.READONLY],
    operation_id="search_subscriptions",
)
def search_subscriptions_endpoint(params: SearchSubscriptionsRequest) -> list[SubscriptionSearchResult]:
    """Search subscriptions with typed filters."""
    stmt = (
        select(SubscriptionTable)
        .options(joinedload(SubscriptionTable.product))
        .order_by(SubscriptionTable.start_date.desc())
        .limit(params.limit)
    )
    if params.status is not None:
        stmt = stmt.where(SubscriptionTable.status == params.status)
    if params.product_type is not None:
        stmt = stmt.join(ProductTable).where(ProductTable.product_type == params.product_type)
    if params.query is not None:
        stmt = stmt.where(SubscriptionTable.description.ilike(f"%{params.query}%"))

    subscriptions = db.session.scalars(stmt).unique().all()
    return [
        SubscriptionSearchResult(
            subscription_id=s.subscription_id,
            description=s.description,
            status=s.status,
            insync=s.insync,
            product_name=s.product.name if s.product else None,
            product_type=s.product.product_type if s.product else None,
            customer_id=s.customer_id,
            start_date=s.start_date,
        )
        for s in subscriptions
    ]

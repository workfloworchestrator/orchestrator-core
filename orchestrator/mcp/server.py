"""MCP server exposing orchestrator-core workflow and subscription operations.

This module creates a FastMCP server that provides tools for:
- Listing and discovering workflows
- Starting, resuming, and aborting workflow processes
- Checking process status and querying recent processes
- Fetching subscription details and available workflows per subscription
- Listing products
"""

import json
from typing import Any
from uuid import UUID

import structlog
from fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable, db
from orchestrator.forms import generate_form
from orchestrator.services.processes import (
    _get_process,
    abort_process,
    load_process,
    resume_process,
    start_process,
)
from orchestrator.services.products import get_products
from orchestrator.services.subscriptions import get_subscription, subscription_workflows
from orchestrator.services.workflows import get_workflows
from orchestrator.utils.enrich_process import enrich_process
from orchestrator.utils.json import json_dumps
from orchestrator.workflows import get_workflow

logger = structlog.get_logger(__name__)

mcp = FastMCP(
    name="orchestrator-core",
    instructions=(
        "Orchestrator Core MCP Server. Provides tools for managing network "
        "automation workflows, processes, subscriptions, and products. "
        "Use list_workflows() to discover available workflows, "
        "get_workflow_form() to inspect required form fields before starting, "
        "and create_workflow() to start a workflow process."
    ),
)


def _serialize(obj: Any) -> str:
    """Serialize an object to a JSON string for MCP tool responses."""
    try:
        return json_dumps(obj)
    except (TypeError, ValueError):
        return str(obj)


def _error_response(error_type: str, message: str, details: Any = None) -> str:
    """Create a standardized error response string."""
    response: dict[str, Any] = {"error": error_type, "message": message}
    if details is not None:
        response["details"] = details
    return json.dumps(response)


# ── Workflow Discovery Tools ─────────────────────────────────────


@mcp.tool()
def list_workflows(
    target: str | None = None,
    is_task: bool | None = None,
) -> str:
    """List all registered workflows in the orchestrator.

    Use this to discover what workflows are available before starting one.

    Args:
        target: Filter by workflow target. Valid values: "create", "modify",
            "terminate", "system", "validate", "reconcile". Leave empty for all.
        is_task: Filter by whether the workflow is a background task (True)
            or a user-facing workflow (False). Leave empty for all.

    Returns:
        JSON array of workflow objects with fields: workflow_id, name, target,
        is_task, description, created_at.
    """
    try:
        with db.database_scope():
            filters: dict[str, Any] = {}
            if target is not None:
                filters["target"] = target.upper()
            if is_task is not None:
                filters["is_task"] = is_task
            workflows = get_workflows(filters=filters if filters else None, include_steps=True)
            result = [
                {
                    "workflow_id": str(wf.workflow_id),
                    "name": wf.name,
                    "target": wf.target,
                    "is_task": wf.is_task,
                    "description": wf.description,
                    "created_at": str(wf.created_at) if wf.created_at else None,
                    "steps": [{"name": s.name} for s in (wf.steps or [])],
                }
                for wf in workflows
            ]
            return json.dumps(result)
    except Exception as e:
        logger.error("list_workflows failed", error=str(e))
        return _error_response("list_workflows_error", str(e))


@mcp.tool()
def get_workflow_form(
    workflow_key: str,
    page_inputs: list[dict[str, Any]] | None = None,
) -> str:
    """Get the JSON Schema of a workflow's form for the next page.

    Call this BEFORE starting a workflow to discover what input fields are required.
    For multi-page forms, pass previously filled pages in page_inputs to get the
    next page's schema.

    Args:
        workflow_key: The workflow name (snake_case, e.g. "create_node",
            "modify_note"). Use list_workflows() to find valid names.
        page_inputs: List of dicts with previously filled form pages.
            Pass [] or None for the first page. Pass [{"field": "value"}]
            to get page 2 after filling page 1, etc.

    Returns:
        JSON object with the form schema including field names, types,
        constraints, and whether more pages follow (hasNext).

    Example:
        # Get first page schema:
        get_workflow_form("modify_note")

        # Get second page after filling first:
        get_workflow_form("modify_note", [{"subscription_id": "abc-123"}])
    """
    try:
        with db.database_scope():
            wf = get_workflow(workflow_key)
            if not wf:
                return _error_response("not_found", f"Workflow '{workflow_key}' does not exist")

            initial_state: dict[str, Any] = {"workflow_name": workflow_key}
            user_inputs = page_inputs or []
            form_schema = generate_form(wf.initial_input_form, initial_state, user_inputs)
            return json.dumps(form_schema, default=str)
    except Exception as e:
        logger.error("get_workflow_form failed", workflow_key=workflow_key, error=str(e))
        return _error_response("form_error", str(e))


@mcp.tool()
def get_subscription_available_workflows(subscription_id: str) -> str:
    """Get workflows available for a specific subscription.

    Shows which workflows can be run on this subscription and why some
    may be blocked (e.g. subscription not in sync, wrong lifecycle state).

    Args:
        subscription_id: UUID of the subscription.

    Returns:
        JSON object with workflow availability per target (create, modify,
        terminate, etc.). Each workflow entry has name, description, and
        optionally a "reason" field explaining why it's blocked.
    """
    try:
        with db.database_scope():
            subscription = get_subscription(UUID(subscription_id))
            result = subscription_workflows(subscription)
            return json.dumps(result, default=str)
    except ValueError as e:
        return _error_response("not_found", f"Subscription not found: {e}")
    except Exception as e:
        logger.error("get_subscription_available_workflows failed", error=str(e))
        return _error_response("subscription_workflows_error", str(e))


# ── Workflow Execution Tools ─────────────────────────────────────


@mcp.tool()
def create_workflow(
    workflow_key: str,
    form_inputs: list[dict[str, Any]],
    user: str = "mcp",
) -> str:
    """Start a new workflow process.

    IMPORTANT: Call get_workflow_form() first to discover required fields.

    Args:
        workflow_key: The workflow name (e.g. "modify_note", "create_node").
            Use list_workflows() to discover available workflow names.
        form_inputs: List of form page dicts. For single-page forms, pass a
            list with one dict. For multi-page forms, include all pages in order.
            Use get_workflow_form() to discover required fields for each page.
        user: Username to attribute the workflow execution to. Defaults to "mcp".

    Returns:
        JSON with process_id on success, or error details on failure.

    Examples:
        # Single-page form:
        create_workflow("modify_note", [{"subscription_id": "abc-123", "note": "Updated"}])

        # Multi-page form (page 1: product selection, page 2: details):
        create_workflow("create_node", [{"product": "prod-uuid"}, {"name": "node1"}])
    """
    try:
        with db.database_scope():
            process_id = start_process(
                workflow_key,
                user_inputs=form_inputs,
                user=user,
            )
            return json.dumps({"process_id": str(process_id), "status": "started"})
    except Exception as e:
        error_str = str(e)
        logger.error("create_workflow failed", workflow_key=workflow_key, error=error_str)
        # FormValidationError from pydantic_forms includes structured validation details
        if hasattr(e, "detail"):
            return _error_response("validation_error", error_str, getattr(e, "detail", None))
        return _error_response("workflow_error", error_str)


@mcp.tool()
def resume_workflow_process(
    process_id: str,
    form_inputs: list[dict[str, Any]] | None = None,
    user: str = "mcp",
) -> str:
    """Resume a suspended or failed workflow process.

    When a process is in SUSPENDED status, it is waiting for user input.
    Use get_process_status() to see the current form schema, then provide
    the required inputs here.

    Args:
        process_id: UUID of the process to resume.
        form_inputs: Form input data for the current suspended step.
            Use get_process_status() to see what fields are needed.
            Pass [{}] to retry a failed process without new input.
        user: Username to attribute the action to. Defaults to "mcp".

    Returns:
        JSON with process_id and status on success, or error details on failure.
    """
    try:
        with db.database_scope():
            process = _get_process(UUID(process_id))
            resume_process(
                process,
                user_inputs=form_inputs,
                user=user,
            )
            return json.dumps({"process_id": process_id, "status": "resumed"})
    except Exception as e:
        logger.error("resume_workflow_process failed", process_id=process_id, error=str(e))
        if hasattr(e, "detail"):
            return _error_response("validation_error", str(e), getattr(e, "detail", None))
        return _error_response("resume_error", str(e))


@mcp.tool()
def abort_workflow_process(
    process_id: str,
    user: str = "mcp",
) -> str:
    """Abort a running or suspended workflow process.

    This will stop the process and set its status to ABORTED.
    This action cannot be undone.

    Args:
        process_id: UUID of the process to abort.
        user: Username to attribute the action to. Defaults to "mcp".

    Returns:
        JSON with process_id and status on success, or error details on failure.
    """
    try:
        with db.database_scope():
            process = _get_process(UUID(process_id))
            abort_process(process, user)
            return json.dumps({"process_id": process_id, "status": "aborted"})
    except Exception as e:
        logger.error("abort_workflow_process failed", process_id=process_id, error=str(e))
        return _error_response("abort_error", str(e))


# ── Process Monitoring Tools ─────────────────────────────────────


@mcp.tool()
def get_process_status(process_id: str) -> str:
    """Get the current status and details of a workflow process.

    If the process is SUSPENDED, the response includes the form schema
    for the input needed to resume it.

    Args:
        process_id: UUID of the process.

    Returns:
        JSON with process details: process_id, workflow_name, last_status,
        last_step, started_at, last_modified_at, created_by, and form
        (if suspended).
    """
    try:
        with db.database_scope():
            process = _get_process(UUID(process_id))
            pstat = load_process(process)
            enriched = enrich_process(process, pstat)

            result: dict[str, Any] = {
                "process_id": str(process.process_id),
                "workflow_name": process.workflow.name if process.workflow else None,
                "last_status": process.last_status,
                "last_step": process.last_step,
                "started_at": str(process.started_at) if process.started_at else None,
                "last_modified_at": str(process.last_modified_at) if process.last_modified_at else None,
                "created_by": process.created_by,
                "is_task": process.is_task,
                "failed_reason": process.failed_reason,
                "traceback": process.traceback,
            }

            # Include form schema if process is suspended
            if enriched.get("form"):
                result["form"] = enriched["form"]

            # Include current state summary (without sensitive data)
            if enriched.get("current_state"):
                result["current_state"] = enriched["current_state"]

            return json.dumps(result, default=str)
    except Exception as e:
        logger.error("get_process_status failed", process_id=process_id, error=str(e))
        return _error_response("process_error", str(e))


@mcp.tool()
def list_recent_processes(
    status: str | None = None,
    workflow_name: str | None = None,
    is_task: bool | None = None,
    limit: int = 20,
) -> str:
    """List recent workflow processes, optionally filtered by status or workflow.

    Args:
        status: Filter by process status. Valid values: "created", "running",
            "suspended", "waiting", "completed", "failed", "aborted",
            "api_unavailable", "inconsistent_data". Leave empty for all.
        workflow_name: Filter by workflow name (e.g. "modify_note").
            Leave empty for all.
        is_task: Filter by whether the process is a background task (True)
            or user-facing (False). Leave empty for all.
        limit: Maximum number of processes to return. Default 20, max 100.

    Returns:
        JSON array of process summaries with: process_id, workflow_name,
        last_status, last_step, started_at, created_by.
    """
    try:
        with db.database_scope():
            limit = min(limit, 100)

            stmt = (
                select(ProcessTable)
                .options(joinedload(ProcessTable.workflow))
                .order_by(ProcessTable.started_at.desc())
                .limit(limit)
            )

            if status is not None:
                stmt = stmt.where(ProcessTable.last_status == status)
            if is_task is not None:
                stmt = stmt.where(ProcessTable.is_task.is_(is_task))
            if workflow_name is not None:
                stmt = stmt.join(WorkflowTable).where(WorkflowTable.name == workflow_name)

            processes = db.session.scalars(stmt).unique().all()

            result = [
                {
                    "process_id": str(p.process_id),
                    "workflow_name": p.workflow.name if p.workflow else None,
                    "last_status": p.last_status,
                    "last_step": p.last_step,
                    "started_at": str(p.started_at) if p.started_at else None,
                    "last_modified_at": str(p.last_modified_at) if p.last_modified_at else None,
                    "created_by": p.created_by,
                    "is_task": p.is_task,
                }
                for p in processes
            ]
            return json.dumps(result)
    except Exception as e:
        logger.error("list_recent_processes failed", error=str(e))
        return _error_response("list_processes_error", str(e))


# ── Subscription Query Tools ─────────────────────────────────────


@mcp.tool()
def get_subscription_details(subscription_id: str) -> str:
    """Get detailed information about a subscription including its product blocks.

    Args:
        subscription_id: UUID of the subscription.

    Returns:
        JSON with subscription details: subscription_id, description, status,
        insync, product name/type, customer_id, start_date, and product block tree.
    """
    try:
        with db.database_scope():
            subscription = get_subscription(UUID(subscription_id))
            result: dict[str, Any] = {
                "subscription_id": str(subscription.subscription_id),
                "description": subscription.description,
                "status": subscription.status,
                "insync": subscription.insync,
                "product": {
                    "product_id": str(subscription.product.product_id),
                    "name": subscription.product.name,
                    "product_type": subscription.product.product_type,
                    "tag": subscription.product.tag,
                    "description": subscription.product.description,
                },
                "customer_id": subscription.customer_id,
                "start_date": str(subscription.start_date) if subscription.start_date else None,
                "end_date": str(subscription.end_date) if subscription.end_date else None,
                "note": subscription.note,
            }
            return json.dumps(result, default=str)
    except ValueError as e:
        return _error_response("not_found", f"Subscription not found: {e}")
    except Exception as e:
        logger.error("get_subscription_details failed", error=str(e))
        return _error_response("subscription_error", str(e))


@mcp.tool()
def search_subscriptions(
    query: str | None = None,
    status: str | None = None,
    product_type: str | None = None,
    limit: int = 20,
) -> str:
    """Search for subscriptions by various criteria.

    Args:
        query: Free-text search query matching subscription description
            or other fields. Leave empty to list all.
        status: Filter by subscription status. Valid values: "initial",
            "provisioning", "active", "disabled", "terminated", "migrating".
        product_type: Filter by product type name.
        limit: Maximum number of results. Default 20, max 100.

    Returns:
        JSON array of subscription summaries with: subscription_id,
        description, status, insync, product_name, product_type, customer_id.
    """
    try:
        with db.database_scope():
            limit = min(limit, 100)

            stmt = (
                select(SubscriptionTable)
                .options(joinedload(SubscriptionTable.product))
                .order_by(SubscriptionTable.start_date.desc())
                .limit(limit)
            )

            if status is not None:
                stmt = stmt.where(SubscriptionTable.status == status)
            if product_type is not None:
                stmt = stmt.join(ProductTable).where(ProductTable.product_type == product_type)
            if query is not None:
                stmt = stmt.where(SubscriptionTable.description.ilike(f"%{query}%"))

            subscriptions = db.session.scalars(stmt).unique().all()

            result = [
                {
                    "subscription_id": str(s.subscription_id),
                    "description": s.description,
                    "status": s.status,
                    "insync": s.insync,
                    "product_name": s.product.name if s.product else None,
                    "product_type": s.product.product_type if s.product else None,
                    "customer_id": s.customer_id,
                    "start_date": str(s.start_date) if s.start_date else None,
                }
                for s in subscriptions
            ]
            return json.dumps(result)
    except Exception as e:
        logger.error("search_subscriptions failed", error=str(e))
        return _error_response("search_error", str(e))


# ── Product Query Tools ──────────────────────────────────────────


@mcp.tool()
def list_products(product_type: str | None = None, tag: str | None = None) -> str:
    """List available products, optionally filtered by type or tag.

    Args:
        product_type: Filter by product type. Leave empty for all.
        tag: Filter by product tag. Leave empty for all.

    Returns:
        JSON array of products with: product_id, name, description,
        product_type, tag, status.
    """
    try:
        with db.database_scope():
            filters = []
            if product_type is not None:
                filters.append(ProductTable.product_type == product_type)
            if tag is not None:
                filters.append(ProductTable.tag == tag)

            products = get_products(filters=filters if filters else None)

            result = [
                {
                    "product_id": str(p.product_id),
                    "name": p.name,
                    "description": p.description,
                    "product_type": p.product_type,
                    "tag": p.tag,
                    "status": p.status,
                }
                for p in products
            ]
            return json.dumps(result, default=str)
    except Exception as e:
        logger.error("list_products failed", error=str(e))
        return _error_response("list_products_error", str(e))


def create_mcp_server() -> FastMCP:
    """Return the configured MCP server instance.

    Returns:
        FastMCP: Configured MCP server instance ready to be mounted.
    """
    return mcp


def create_mcp_app(auth_manager: Any = None) -> Any:
    """Create the MCP ASGI app for mounting in FastAPI.

    Returns a StarletteWithLifespan instance. Lifespan is managed
    automatically by Starlette's mount() lifespan forwarding (Starlette ≥0.37).

    Args:
        auth_manager: The AuthManager instance from the parent OrchestratorCore.
            If provided, all MCP requests will require valid Bearer token
            authentication using the same pluggable auth backend as the REST API.
            If None, the MCP server runs without authentication (development only).

    Returns:
        StarletteWithLifespan: The MCP ASGI app, optionally configured with
        authentication middleware.
    """
    mcp_app = mcp.http_app(path="/")

    if auth_manager is not None:
        from orchestrator.mcp.auth import MCPAuthMiddleware

        mcp_app.add_middleware(MCPAuthMiddleware, auth_manager=auth_manager)
        logger.info("MCP server configured with authentication middleware")
    else:
        logger.warning("MCP server running WITHOUT authentication")

    return mcp_app

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
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from orchestrator.core.agent_tags import AgentTag
from orchestrator.core.api.error_handling import raise_status
from orchestrator.core.db import ProcessTable, ProductTable, SearchQueryTable, SubscriptionTable, WorkflowTable, db
from orchestrator.core.schemas.mcp_search import (
    AggregateRow,
    AggregateToolRequest,
    AggregateToolResponse,
    DiscoverFilterPathsRequest,
    ExportQueryRequest,
    ExportQueryResponse,
    FieldPathDiscovery,
    ResolvedCandidate,
    ResolveEntityRequest,
    ResolveEntityResponse,
    SearchToolRequest,
    SearchToolResponse,
    SearchToolResultItem,
)
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
from orchestrator.core.search.aggregations import FieldAggregation
from orchestrator.core.search.core.exceptions import QueryStateNotFoundError
from orchestrator.core.search.core.types import FilterOp
from orchestrator.core.search.entity_lookup import IdForm, _classify_id, resolve_entity_id_prefix
from orchestrator.core.search.filters.definitions import generate_definitions
from orchestrator.core.search.query import QueryState, engine
from orchestrator.core.search.query.builder import build_paths_query, process_path_rows
from orchestrator.core.search.query.exceptions import PathNotFoundError, QueryValidationError
from orchestrator.core.search.query.queries import AggregateQuery, CountQuery, SelectQuery
from orchestrator.core.search.query.validation import (
    validate_aggregation_field,
    validate_filter_tree,
    validate_grouping_fields,
    validate_order_by_fields,
    validate_temporal_grouping_field,
)
from orchestrator.core.services.processes import _get_process, load_process
from orchestrator.core.services.subscriptions import get_subscription, subscription_workflows
from orchestrator.core.services.workflows import get_workflows
from orchestrator.core.utils.enrich_process import enrich_process
from orchestrator.core.workflows import get_workflow

logger = structlog.get_logger(__name__)

_PREFIX_MATCH_LIMIT = 10

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


# ---------------------------------------------------------------------------
# Search-engine tools
#
# These expose orchestrator-core's search/aggregation engine as self-contained
# MCP tools. They were previously implemented inside orchestrator-agent, which
# reached into the engine directly; moving them here lets any agent drive search
# over MCP with no DB/engine coupling. Each search/aggregate call persists its
# query (run_id=NULL) so the returned query_id can drive export_query.
# ---------------------------------------------------------------------------


def _persist_query(
    query: SelectQuery | CountQuery | AggregateQuery,
    query_embedding: list[float] | None = None,
) -> UUID:
    """Persist an executed query as a standalone row (run_id=NULL); return its query_id."""
    state = QueryState(query=query, query_embedding=query_embedding)
    row = SearchQueryTable.from_state(state=state, run_id=None, query_number=1)
    db.session.add(row)
    db.session.commit()
    return row.query_id


@router.post(
    "/search",
    response_model=SearchToolResponse,
    tags=[AgentTag.EXPOSED, AgentTag.LARGE, AgentTag.READONLY],
    operation_id="search",
)
async def search_endpoint(params: SearchToolRequest) -> SearchToolResponse:
    """Find and rank entities (subscriptions, products, workflows, processes).

    Build structured ``filters`` with discover_filter_paths/get_valid_operators,
    and/or pass ``query_text`` for semantic/fuzzy ranking. Returns ranked rows plus
    a ``query_id`` that export_query can turn into a CSV download. For counts or
    statistics use ``aggregate`` instead.
    """
    if params.filters is not None:
        try:
            await validate_filter_tree(params.filters, params.entity_type)
        except PathNotFoundError as exc:
            raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, f"{exc} Use discover_filter_paths to find valid paths.")
        except QueryValidationError as exc:
            raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    try:
        query = SelectQuery(
            entity_type=params.entity_type,
            query_text=params.query_text,
            filters=params.filters,
            limit=params.limit,
            retriever=params.retriever,
        )
    except ValidationError as exc:
        raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    try:
        response = await engine.execute_search(query, db.session)
    except ValueError as exc:
        raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    query_id = _persist_query(query, response.query_embedding)
    return SearchToolResponse(
        query_id=query_id,
        entity_type=params.entity_type,
        returned=len(response.results),
        has_more=response.has_more,
        search_type=response.metadata.search_type,
        results=[
            SearchToolResultItem(
                entity_id=r.entity_id,
                entity_type=r.entity_type,
                title=r.entity_title,
                score=r.score,
            )
            for r in response.results
        ],
    )


def _build_aggregate_query(params: AggregateToolRequest) -> CountQuery | AggregateQuery:
    """Construct the CountQuery/AggregateQuery, surfacing model errors as 422s."""
    if params.operation == "aggregate" and not params.aggregations:
        raise_status(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "operation='aggregate' requires at least one aggregation (SUM/AVG/MIN/MAX/COUNT). "
            "Use operation='count' to only count rows.",
        )
    try:
        if params.operation == "aggregate":
            return AggregateQuery(
                entity_type=params.entity_type,
                filters=params.filters,
                aggregations=params.aggregations or [],
                group_by=params.group_by,
                temporal_group_by=params.temporal_group_by,
                cumulative=params.cumulative,
                order_by=params.order_by,
            )
        return CountQuery(
            entity_type=params.entity_type,
            filters=params.filters,
            group_by=params.group_by,
            temporal_group_by=params.temporal_group_by,
            cumulative=params.cumulative,
            order_by=params.order_by,
        )
    except ValidationError as exc:
        raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))


@router.post(
    "/aggregate",
    response_model=AggregateToolResponse,
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="aggregate",
)
async def aggregate_endpoint(params: AggregateToolRequest) -> AggregateToolResponse:
    """Count entities or compute statistics (SUM/AVG/MIN/MAX), optionally grouped.

    operation='count' counts rows (optionally grouped by ``group_by`` / ``temporal_group_by``);
    operation='aggregate' computes ``aggregations`` over the matching rows. Validate
    field paths with discover_filter_paths first.
    """
    try:
        validate_grouping_fields(params.group_by or [])
        for agg in params.aggregations or []:
            if isinstance(agg, FieldAggregation):
                validate_aggregation_field(agg.type, agg.field)
        for tg in params.temporal_group_by or []:
            validate_temporal_grouping_field(tg.field)
        validate_order_by_fields(params.order_by)
    except PathNotFoundError as exc:
        raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, f"{exc} Use discover_filter_paths to find valid paths.")
    except QueryValidationError as exc:
        raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    if params.filters is not None:
        try:
            await validate_filter_tree(params.filters, params.entity_type)
        except (PathNotFoundError, QueryValidationError) as exc:
            raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    query = _build_aggregate_query(params)
    response = await engine.execute_aggregation(query, db.session)
    query_id = _persist_query(query)
    return AggregateToolResponse(
        query_id=query_id,
        total_results=response.total_results,
        visualization=str(response.visualization_type.type),
        results=[AggregateRow(group_values=r.group_values, aggregations=r.aggregations) for r in response.results],
    )


@router.post(
    "/discover_filter_paths",
    response_model=dict[str, FieldPathDiscovery],
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="discover_filter_paths",
)
async def discover_filter_paths_endpoint(params: DiscoverFilterPathsRequest) -> dict[str, FieldPathDiscovery]:
    """Discover filterable paths for field names, to build a filter tree for search/aggregate."""
    results: dict[str, FieldPathDiscovery] = {}
    for field_name in params.field_names:
        stmt = build_paths_query(entity_type=params.entity_type, prefix="", q=field_name).limit(100)
        rows = db.session.execute(stmt).all()
        leaves, components = process_path_rows(rows)

        matching_leaves = [
            {"name": leaf.name, "value_kind": leaf.ui_types, "paths": leaf.paths}
            for leaf in leaves
            if field_name.lower() in leaf.name.lower()
        ]
        matching_components = [
            {"name": comp.name, "value_kind": comp.ui_types}
            for comp in components
            if field_name.lower() in comp.name.lower()
        ]
        if not matching_leaves and not matching_components:
            results[field_name] = FieldPathDiscovery(
                status="NOT_FOUND",
                guidance=f"No filterable paths found containing '{field_name}'. Do not create a filter for this.",
            )
        else:
            results[field_name] = FieldPathDiscovery(
                status="OK",
                guidance=(
                    f"Found {len(matching_leaves)} field(s) and "
                    f"{len(matching_components)} component(s) for '{field_name}'."
                ),
                leaves=matching_leaves,
                components=matching_components,
            )
    return results


@router.post(
    "/get_valid_operators",
    response_model=dict[str, list[FilterOp]],
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="get_valid_operators",
)
def get_valid_operators_endpoint() -> dict[str, list[FilterOp]]:
    """Return the mapping of field types to their valid filter operators."""
    definitions = generate_definitions()
    return {
        ui_type.value: type_def.operators for ui_type, type_def in definitions.items() if hasattr(type_def, "operators")
    }


@router.post(
    "/resolve_entity",
    response_model=ResolveEntityResponse,
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="resolve_entity",
)
def resolve_entity_endpoint(params: ResolveEntityRequest) -> ResolveEntityResponse:
    """Resolve a full UUID or partial id-prefix to one entity, or list candidates to disambiguate."""
    form, normalized = _classify_id(params.id_or_prefix)
    if form is IdForm.NON_HEX:
        return ResolveEntityResponse(
            status="not_found",
            entity_type=params.entity_type,
            message=f"'{params.id_or_prefix.strip()}' is not a UUID; search by name instead.",
        )
    if form is IdForm.TOO_SHORT:
        return ResolveEntityResponse(
            status="not_found",
            entity_type=params.entity_type,
            message="Need at least 4 characters of the id to look it up.",
        )

    matches = resolve_entity_id_prefix(db.session, params.entity_type, normalized, limit=_PREFIX_MATCH_LIMIT)
    if not matches:
        return ResolveEntityResponse(
            status="not_found",
            entity_type=params.entity_type,
            message=f"No {params.entity_type.value} found with id starting with {normalized}.",
        )
    if len(matches) == 1:
        return ResolveEntityResponse(
            status="unique",
            entity_type=params.entity_type,
            entity_id=matches[0].entity_id,
            title=matches[0].title,
            message=f"Resolved to a single {params.entity_type.value}.",
        )

    capped = matches[:_PREFIX_MATCH_LIMIT]
    message = f"Multiple {params.entity_type.value} ids start with {normalized}; ask the user to refine or pick one."
    if len(matches) > _PREFIX_MATCH_LIMIT:
        message += f" Showing the first {_PREFIX_MATCH_LIMIT}."
    return ResolveEntityResponse(
        status="candidates",
        entity_type=params.entity_type,
        candidates=[ResolvedCandidate(entity_id=m.entity_id, title=m.title) for m in capped],
        message=message,
    )


@router.post(
    "/export_query",
    response_model=ExportQueryResponse,
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
    operation_id="export_query",
)
def export_query_endpoint(params: ExportQueryRequest) -> ExportQueryResponse:
    """Prepare a CSV export download for a previously executed search ``query_id``."""
    try:
        QueryState.load_from_id(str(params.query_id), SelectQuery)
    except QueryStateNotFoundError:
        raise_status(HTTPStatus.NOT_FOUND, f"Query {params.query_id} not found. Run a search first.")
    return ExportQueryResponse(
        query_id=params.query_id,
        download_path=f"/api/search/queries/{params.query_id}/export",
        message="Export ready. Provide this link to the user to download the results as CSV.",
    )

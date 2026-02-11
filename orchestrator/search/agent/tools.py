# Copyright 2019-2025 SURF, GÉANT.
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

import json
from typing import Any, cast
from uuid import UUID

import structlog
from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.toolsets import FunctionToolset

from orchestrator.api.api_v1.endpoints.search import (
    get_definitions,
    list_paths,
)
from orchestrator.db import db
from orchestrator.search.agent.environment import ToolStep
from orchestrator.search.agent.handlers import (
    execute_aggregation_with_persistence,
    execute_search_with_persistence,
)
from orchestrator.search.agent.state import SearchState
from orchestrator.search.aggregations import Aggregation, FieldAggregation, TemporalGrouping
from orchestrator.search.core.types import EntityType, FilterOp
from orchestrator.search.filters import FilterTree
from orchestrator.search.query import engine
from orchestrator.search.query.exceptions import PathNotFoundError, QueryValidationError
from orchestrator.search.query.export import fetch_export_data
from orchestrator.search.query.mixins import OrderBy
from orchestrator.search.query.queries import AggregateQuery, CountQuery, Query, SelectQuery
from orchestrator.search.query.results import AggregationResponse, AggregationResult, ExportData, VisualizationType
from orchestrator.search.query.state import QueryState
from orchestrator.search.query.validation import (
    validate_aggregation_field,
    validate_filter_tree,
    validate_grouping_fields,
    validate_order_by_fields,
    validate_temporal_grouping_field,
)
from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)


# Node-specific toolsets for graph control flow
filter_building_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=2)
aggregation_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=2)
search_execution_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=2)
aggregation_execution_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=2)
result_actions_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=2)


@filter_building_toolset.tool
async def set_filter_tree(
    ctx: RunContext[StateDeps[SearchState]],
    filters: FilterTree | None,
) -> Query:
    """Replace current filters atomically with a full FilterTree, or clear with None.

    See FilterTree model for structure, operators, and examples.

    Returns the updated Query as structured output.
    """
    if ctx.deps.state.query is None:
        raise ModelRetry("Search query is not initialized. PlannerNode should have initialized it.")

    entity_type = ctx.deps.state.query.entity_type

    logger.debug(
        "Setting filter tree",
        entity_type=entity_type.value,
        has_filters=filters is not None,
        filter_summary=f"{len(filters.get_all_leaves())} filters" if filters else "no filters",
    )

    try:
        await validate_filter_tree(filters, entity_type)
    except PathNotFoundError as e:
        logger.debug(f"{PathNotFoundError.__name__}: {str(e)}")
        raise ModelRetry(f"{str(e)} Use discover_filter_paths tool to find valid paths.")
    except QueryValidationError as e:
        # ModelRetry will trigger an agent retry, containing the specific validation error.
        logger.debug(f"Query validation failed: {str(e)}")
        raise ModelRetry(str(e))
    except Exception as e:
        logger.error("Unexpected Filter validation exception", error=str(e))
        raise ModelRetry(f"Filter validation failed: {str(e)}. Please check your filter structure and try again.")

    updated_query = cast(Query, ctx.deps.state.query).model_copy(update={"filters": filters})
    ctx.deps.state.query = updated_query

    return updated_query


@search_execution_toolset.tool
async def run_search(
    ctx: RunContext[StateDeps[SearchState]],
    limit: int = 10,
) -> AggregationResponse:
    """Execute a search to find and rank entities.

    Use this tool for SELECT action to find entities matching your criteria.
    For counting or computing statistics, use run_aggregation instead.
    """
    query = cast(SelectQuery, cast(Query, ctx.deps.state.query).model_copy(update={"limit": limit}))

    search_response, run_id, query_id = await execute_search_with_persistence(query, db.session, ctx.deps.state.run_id)

    ctx.deps.state.run_id = run_id

    # Record tool step with query_id
    ctx.deps.state.environment.record_tool_step(
        ToolStep(
            step_type="run_search",
            description=f"Searched {len(search_response.results)} {query.entity_type.value}",
            entity_type=query.entity_type.value,
            results_count=len(search_response.results),
            query_operation=query.query_operation.value,
            query_snapshot=query.model_dump(),
            query_id=query_id,
            success=True,
        )
    )

    # Convert SearchResults to AggregationResults for consistent rendering
    aggregation_results = [
        AggregationResult(
            group_values={
                "entity_id": result.entity_id,
                "title": result.entity_title,
                "entity_type": result.entity_type.value,
            },
            aggregations={"score": result.score},
        )
        for result in search_response.results
    ]

    # For now use the default table visualization for search results
    aggregation_response = AggregationResponse(
        results=aggregation_results,
        total_groups=len(aggregation_results),
        metadata=search_response.metadata,
        visualization_type=VisualizationType(type="table"),
    )

    logger.debug(
        "Search completed",
        total_count=len(search_response.results),
        query_id=str(query_id),
    )

    # Note: State is automatically tracked by AG-UI through StateDeps
    return aggregation_response


@aggregation_execution_toolset.tool
async def run_aggregation(
    ctx: RunContext[StateDeps[SearchState]],
    visualization_type: VisualizationType,
) -> AggregationResponse:
    """Execute an aggregation to compute counts or statistics over entities.

    Use this tool for COUNT or AGGREGATE actions after setting up:
    - Grouping fields with set_grouping or set_temporal_grouping
    - Aggregation functions with set_aggregations (for AGGREGATE action)
    """
    query = cast(CountQuery | AggregateQuery, ctx.deps.state.query)

    # Validate AGGREGATE action has aggregations set
    if isinstance(query, AggregateQuery) and not query.aggregations:
        raise ModelRetry(
            "AGGREGATE action requires calling set_aggregations() first to specify which numeric operations to compute (SUM, AVG, MIN, MAX). "
            "If you just want to count rows, use COUNT action instead."
        )

    logger.debug(
        "Executing aggregation",
        search_entity_type=query.entity_type.value,
        has_filters=query.filters is not None,
        query_operation=query.query_operation,
    )

    aggregation_response, run_id, query_id = await execute_aggregation_with_persistence(
        query, db.session, ctx.deps.state.run_id
    )

    ctx.deps.state.run_id = run_id

    # Record tool step with query_id
    ctx.deps.state.environment.record_tool_step(
        ToolStep(
            step_type="run_aggregation",
            description=f"Aggregated {aggregation_response.total_groups} groups for {query.entity_type.value}",
            entity_type=query.entity_type.value,
            results_count=aggregation_response.total_groups,
            query_operation=query.query_operation.value,
            query_snapshot=query.model_dump(),
            query_id=query_id,
            success=True,
        )
    )

    aggregation_response.visualization_type = visualization_type

    logger.debug(
        "Aggregation completed",
        total_groups=aggregation_response.total_groups,
        visualization_type=visualization_type.type,
        query_id=str(query_id),
    )

    return aggregation_response


@filter_building_toolset.tool
async def discover_filter_paths(
    ctx: RunContext[StateDeps[SearchState]],
    field_names: list[str],
    entity_type: EntityType | None = None,
) -> dict[str, dict[str, Any]]:
    """Discovers available filter paths for a list of field names.

    Returns a dictionary where each key is a field_name from the input list and
    the value is its discovery result.
    """
    if not entity_type:
        if ctx.deps.state.query:
            entity_type = ctx.deps.state.query.entity_type
        else:
            raise ModelRetry("Entity type not specified and no query in state. PlannerNode should have initialized it.")

    all_results = {}
    for field_name in field_names:
        paths_response = await list_paths(prefix="", q=field_name, entity_type=entity_type, limit=100)

        matching_leaves = []
        for leaf in paths_response.leaves:
            if field_name.lower() in leaf.name.lower():
                matching_leaves.append(
                    {
                        "name": leaf.name,
                        "value_kind": leaf.ui_types,
                        "paths": leaf.paths,
                    }
                )

        matching_components = []
        for comp in paths_response.components:
            if field_name.lower() in comp.name.lower():
                matching_components.append(
                    {
                        "name": comp.name,
                        "value_kind": comp.ui_types,
                    }
                )

        result_for_field: dict[str, Any]
        if not matching_leaves and not matching_components:
            result_for_field = {
                "status": "NOT_FOUND",
                "guidance": f"No filterable paths found containing '{field_name}'. Do not create a filter for this.",
                "leaves": [],
                "components": [],
            }
        else:
            result_for_field = {
                "status": "OK",
                "guidance": f"Found {len(matching_leaves)} field(s) and {len(matching_components)} component(s) for '{field_name}'.",
                "leaves": matching_leaves,
                "components": matching_components,
            }

        all_results[field_name] = result_for_field
    return all_results


@filter_building_toolset.tool
async def get_valid_operators() -> dict[str, list[FilterOp]]:
    """Gets the mapping of field types to their valid filter operators."""
    definitions = await get_definitions()

    operator_map = {}
    for ui_type, type_def in definitions.items():
        key = ui_type.value

        if hasattr(type_def, "operators"):
            operator_map[key] = type_def.operators
    return operator_map


@result_actions_toolset.tool
async def fetch_entity_details(
    ctx: RunContext[StateDeps[SearchState]],
    query_id: UUID,
    limit: int = 10,
) -> str:
    """Fetch detailed entity information to answer user questions.

    Use this tool when you need detailed information about entities from the search results
    to answer the user's question. This provides the same detailed data that would be
    included in an export (e.g., subscription status, product details, workflow info, etc.).

    Args:
        ctx: Runtime context for agent (injected).
        query_id: ID of the query to fetch details from. Extract from conversation history.
        limit: Maximum number of entities to fetch details for (default 10).

    Returns:
        JSON string containing detailed entity information.
    """
    qid = query_id

    # Load the saved query and re-execute it to get entity IDs
    query_state = QueryState.load_from_id(qid, SelectQuery)
    query = query_state.query.model_copy(update={"limit": limit})
    search_response = await engine.execute_search(query, db.session)
    entity_ids = [r.entity_id for r in search_response.results]

    if not entity_ids:
        return json.dumps({"message": "No entities found in search results."})

    entity_type = query.entity_type

    logger.debug(
        "Fetching detailed entity data",
        entity_type=entity_type.value,
        entity_count=len(entity_ids),
        query_id=str(qid),
    )

    detailed_data = fetch_export_data(entity_type, entity_ids)

    # Record tool step
    ctx.deps.state.environment.record_tool_step(
        ToolStep(
            step_type="fetch_entity_details",
            description=f"Fetched details for {len(entity_ids)} {entity_type.value} entities",
            entity_type=entity_type.value,
            results_count=len(entity_ids),
            query_id=query_id,
            success=True,
        )
    )

    return json.dumps(detailed_data, indent=2)


@result_actions_toolset.tool
async def prepare_export(
    ctx: RunContext[StateDeps[SearchState]],
    query_id: UUID,
) -> ExportData:
    """Prepares export URL for a search query.

    Args:
        ctx: Runtime context for agent (injected).
        query_id: ID of the query to export. Extract from conversation history.

    Returns:
        Export data which is displayed directly in the UI.
    """

    logger.debug(
        "Prepared query for export",
        query_id=str(query_id),
    )

    download_url = f"{app_settings.BASE_URL}/api/search/queries/{query_id}/export"

    export_data = ExportData(
        query_id=str(query_id),
        download_url=download_url,
        message="Export ready for download.",
    )

    # Record tool step
    ctx.deps.state.environment.record_tool_step(
        ToolStep(
            step_type="prepare_export",
            description=f"Prepared export for query {query_id}",
            query_id=query_id,
            success=True,
        )
    )

    logger.debug("Export prepared", query_id=export_data.query_id)

    return export_data


@aggregation_toolset.tool
async def set_grouping(
    ctx: RunContext[StateDeps[SearchState]],
    group_by_paths: list[str],
    order_by: list[OrderBy] | None = None,
) -> Query:
    """Set which field paths to group results by for aggregation.

    Only used with COUNT or AGGREGATE actions. Paths must exist in the schema; use discover_filter_paths to verify.
    Optionally specify ordering for the grouped results.

    For order_by: You can order by grouping field paths OR aggregation aliases (e.g., 'count').
    Grouping field paths will be validated; aggregation aliases cannot be validated until execution.

    Returns the updated Query as structured output.
    """
    try:
        validate_grouping_fields(group_by_paths)
        validate_order_by_fields(order_by)
    except PathNotFoundError as e:
        raise ModelRetry(f"{str(e)} Use discover_filter_paths to find valid paths.")
    except Exception as e:
        raise ModelRetry(f"Validation failed: {str(e)}")

    update_dict: dict[str, Any] = {"group_by": group_by_paths}
    if order_by is not None:
        update_dict["order_by"] = order_by

    try:
        updated_query = cast(Query, ctx.deps.state.query).model_copy(update=update_dict)
        ctx.deps.state.query = updated_query
    except ValidationError as e:
        raise ModelRetry(str(e))

    logger.debug(f"Grouping set by {len(group_by_paths)} field(s): {', '.join(group_by_paths)}")
    return updated_query


@aggregation_toolset.tool
async def set_aggregations(
    ctx: RunContext[StateDeps[SearchState]],
    aggregations: list[Aggregation],
) -> Query:
    """Define what aggregations to compute over the matching records.

    Only used with AGGREGATE action. See Aggregation model (CountAggregation, FieldAggregation) for structure and field requirements.

    Returns the updated Query as structured output.
    """
    # Validate field paths for FieldAggregations
    try:
        for agg in aggregations:
            if isinstance(agg, FieldAggregation):
                validate_aggregation_field(agg.type, agg.field)
    except PathNotFoundError as e:
        raise ModelRetry(
            f"{str(e)} "
            f"You MUST call discover_filter_paths first to find valid fields. "
            f"If the field truly doesn't exist, inform the user that this data is not available."
        )
    except QueryValidationError as e:
        raise ModelRetry(f"{str(e)}")

    try:
        updated_query = cast(Query, ctx.deps.state.query).model_copy(update={"aggregations": aggregations})
        ctx.deps.state.query = updated_query
    except ValidationError as e:
        raise ModelRetry(str(e))

    logger.debug(f"Aggregations configured: {len(aggregations)} aggregation(s)")
    return updated_query


@aggregation_toolset.tool
async def set_temporal_grouping(
    ctx: RunContext[StateDeps[SearchState]],
    temporal_groups: list[TemporalGrouping],
    cumulative: bool = False,
    order_by: list[OrderBy] | None = None,
) -> Query:
    """Set temporal grouping to group datetime fields by time periods.

    Only used with COUNT or AGGREGATE actions. See TemporalGrouping model for structure, periods, and examples.
    Optionally enable cumulative aggregations (running totals) and specify ordering.

    For order_by: You can order by temporal field paths OR aggregation aliases (e.g., 'count').
    Temporal field paths will be validated; aggregation aliases cannot be validated until execution.

    Returns the updated Query as structured output.
    """
    try:
        for tg in temporal_groups:
            validate_temporal_grouping_field(tg.field)
        validate_order_by_fields(order_by)
    except PathNotFoundError as e:
        raise ModelRetry(f"{str(e)} Use discover_filter_paths to find valid paths.")
    except QueryValidationError as e:
        raise ModelRetry(f"{str(e)} Use discover_filter_paths to find datetime fields.")

    update_dict: dict[str, Any] = {"temporal_group_by": temporal_groups}
    if cumulative:
        update_dict["cumulative"] = cumulative
    if order_by is not None:
        update_dict["order_by"] = order_by

    try:
        updated_query = cast(Query, ctx.deps.state.query).model_copy(update=update_dict)
        ctx.deps.state.query = updated_query
    except ValidationError as e:
        raise ModelRetry(str(e))

    temporal_desc = ", ".join(f"{tg.field} by {tg.period}" for tg in temporal_groups)
    cumulative_text = " (cumulative)" if cumulative else ""
    logger.debug(f"Temporal grouping set: {temporal_desc}{cumulative_text}")
    return updated_query

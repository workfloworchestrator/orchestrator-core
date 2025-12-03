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

import structlog
from ag_ui.core import EventType, StateSnapshotEvent
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.toolsets import FunctionToolset

from orchestrator.api.api_v1.endpoints.search import (
    get_definitions,
    list_paths,
)
from orchestrator.db import db
from orchestrator.search.agent.handlers import (
    execute_aggregation_with_persistence,
    execute_search_with_persistence,
)
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.validation import require_action
from orchestrator.search.aggregations import Aggregation, FieldAggregation, TemporalGrouping
from orchestrator.search.core.types import ActionType, EntityType, FilterOp
from orchestrator.search.filters import FilterTree
from orchestrator.search.query import engine
from orchestrator.search.query.exceptions import PathNotFoundError, QueryValidationError
from orchestrator.search.query.export import fetch_export_data
from orchestrator.search.query.queries import AggregateQuery, CountQuery, Query, SelectQuery
from orchestrator.search.query.results import AggregationResponse, AggregationResult, ExportData, VisualizationType
from orchestrator.search.query.state import QueryState
from orchestrator.search.query.validation import (
    validate_aggregation_field,
    validate_filter_path,
    validate_filter_tree,
    validate_temporal_grouping_field,
)
from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)

search_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=1)


def last_user_message(ctx: RunContext[StateDeps[SearchState]]) -> str | None:
    for msg in reversed(ctx.messages):
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return None


@search_toolset.tool
async def start_new_search(
    ctx: RunContext[StateDeps[SearchState]],
    entity_type: EntityType,
    action: ActionType = ActionType.SELECT,
) -> StateSnapshotEvent:
    """Starts a completely new search, clearing all previous state.

    This MUST be the first tool called when the user asks for a NEW search.
    Warning: This will erase any existing filters, results, and search state.
    """
    final_query = last_user_message(ctx) or ""

    logger.debug(
        "Starting new search",
        entity_type=entity_type.value,
        action=action,
        query=final_query,
    )

    # Clear all state
    ctx.deps.state.results_count = None
    ctx.deps.state.action = action

    # Create the appropriate query object based on action
    if action == ActionType.SELECT:
        ctx.deps.state.query = SelectQuery(
            entity_type=entity_type,
            query_text=final_query,
        )
    elif action == ActionType.COUNT:
        ctx.deps.state.query = CountQuery(
            entity_type=entity_type,
        )
    else:  # ActionType.AGGREGATE
        ctx.deps.state.query = AggregateQuery(
            entity_type=entity_type,
            aggregations=[],  # Will be set by set_aggregations tool
        )

    logger.debug("New search started", action=action.value, query_type=type(ctx.deps.state.query).__name__)

    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )


@search_toolset.tool(retries=2)
async def set_filter_tree(
    ctx: RunContext[StateDeps[SearchState]],
    filters: FilterTree | None,
) -> StateSnapshotEvent:
    """Replace current filters atomically with a full FilterTree, or clear with None.

    See FilterTree model for structure, operators, and examples.
    """
    if ctx.deps.state.query is None:
        raise ModelRetry("Search query is not initialized. Call start_new_search first.")

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

    ctx.deps.state.query = cast(Query, ctx.deps.state.query).model_copy(update={"filters": filters})

    # Use snapshot to workaround state persistence issue
    # TODO: Fix root cause; state tree may be empty on frontend when parameters are being set
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )


@search_toolset.tool
@require_action(ActionType.SELECT)
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
    ctx.deps.state.query_id = query_id
    ctx.deps.state.results_count = len(search_response.results)

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
        total_count=ctx.deps.state.results_count,
        query_id=str(query_id),
    )

    return aggregation_response


@search_toolset.tool
@require_action(ActionType.COUNT, ActionType.AGGREGATE)
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

    logger.debug(
        "Executing aggregation",
        search_entity_type=query.entity_type.value,
        has_filters=query.filters is not None,
        action=query.action,
    )

    aggregation_response, run_id, query_id = await execute_aggregation_with_persistence(
        query, db.session, ctx.deps.state.run_id
    )

    ctx.deps.state.run_id = run_id
    ctx.deps.state.query_id = query_id
    ctx.deps.state.results_count = aggregation_response.total_groups

    aggregation_response.visualization_type = visualization_type

    logger.debug(
        "Aggregation completed",
        total_groups=aggregation_response.total_groups,
        visualization_type=visualization_type.type,
        query_id=str(query_id),
    )

    return aggregation_response


@search_toolset.tool
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
            raise ModelRetry("Entity type not specified and no query in state. Call start_new_search first.")

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
    logger.debug("Returning found fieldname - path mapping", all_results=all_results)
    return all_results


@search_toolset.tool
async def get_valid_operators() -> dict[str, list[FilterOp]]:
    """Gets the mapping of field types to their valid filter operators."""
    definitions = await get_definitions()

    operator_map = {}
    for ui_type, type_def in definitions.items():
        key = ui_type.value

        if hasattr(type_def, "operators"):
            operator_map[key] = type_def.operators
    return operator_map


@search_toolset.tool
async def fetch_entity_details(
    ctx: RunContext[StateDeps[SearchState]],
    limit: int = 10,
) -> str:
    """Fetch detailed entity information to answer user questions.

    Use this tool when you need detailed information about entities from the search results
    to answer the user's question. This provides the same detailed data that would be
    included in an export (e.g., subscription status, product details, workflow info, etc.).

    Args:
        ctx: Runtime context for agent (injected).
        limit: Maximum number of entities to fetch details for (default 10).

    Returns:
        JSON string containing detailed entity information.

    Raises:
        ModelRetry: If no search has been executed.
    """
    if ctx.deps.state.query_id is None:
        raise ModelRetry("No query_id found. Run a search first.")

    # Load the saved query and re-execute it to get entity IDs
    query_state = QueryState.load_from_id(ctx.deps.state.query_id, SelectQuery)
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
    )

    detailed_data = fetch_export_data(entity_type, entity_ids)

    return json.dumps(detailed_data, indent=2)


@search_toolset.tool
@require_action(ActionType.SELECT)
async def prepare_export(
    ctx: RunContext[StateDeps[SearchState]],
) -> ExportData:
    """Prepares export URL using the last executed search query.

    Returns export data which is displayed directly in the UI.
    """
    if not ctx.deps.state.query_id or not ctx.deps.state.run_id:
        raise ModelRetry("No search has been executed yet. Run a search first before exporting.")

    logger.debug(
        "Prepared query for export",
        query_id=str(ctx.deps.state.query_id),
    )

    download_url = f"{app_settings.BASE_URL}/api/search/queries/{ctx.deps.state.query_id}/export"

    export_data = ExportData(
        query_id=str(ctx.deps.state.query_id),
        download_url=download_url,
        message="Export ready for download.",
    )

    logger.debug("Export prepared", query_id=export_data.query_id)

    return export_data


@search_toolset.tool(retries=2)
@require_action(ActionType.COUNT, ActionType.AGGREGATE)
async def set_grouping(
    ctx: RunContext[StateDeps[SearchState]],
    group_by_paths: list[str],
) -> StateSnapshotEvent:
    """Set which field paths to group results by for aggregation.

    Only used with COUNT or AGGREGATE actions. Paths must exist in the schema; use discover_filter_paths to verify.
    """
    for path in group_by_paths:
        field_type = validate_filter_path(path)
        if field_type is None:
            raise ModelRetry(
                f"Path '{path}' not found in database schema. "
                f"Use discover_filter_paths(['{path.split('.')[-1]}']) to find valid paths."
            )

    ctx.deps.state.query = cast(Query, ctx.deps.state.query).model_copy(update={"group_by": group_by_paths})

    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )


@search_toolset.tool(retries=2)
@require_action(ActionType.AGGREGATE)
async def set_aggregations(
    ctx: RunContext[StateDeps[SearchState]],
    aggregations: list[Aggregation],
) -> StateSnapshotEvent:
    """Define what aggregations to compute over the matching records.

    Only used with AGGREGATE action. See Aggregation model (CountAggregation, FieldAggregation) for structure and field requirements.
    """
    # Validate field paths for FieldAggregations
    try:
        for agg in aggregations:
            if isinstance(agg, FieldAggregation):
                validate_aggregation_field(agg.type, agg.field)
    except ValueError as e:
        raise ModelRetry(f"{str(e)} Use discover_filter_paths to find valid paths.")

    ctx.deps.state.query = cast(Query, ctx.deps.state.query).model_copy(update={"aggregations": aggregations})

    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )


@search_toolset.tool(retries=2)
@require_action(ActionType.COUNT, ActionType.AGGREGATE)
async def set_temporal_grouping(
    ctx: RunContext[StateDeps[SearchState]],
    temporal_groups: list[TemporalGrouping],
) -> StateSnapshotEvent:
    """Set temporal grouping to group datetime fields by time periods.

    Only used with COUNT or AGGREGATE actions. See TemporalGrouping model for structure, periods, and examples.
    """
    # Validate that fields exist and are datetime types
    try:
        for tg in temporal_groups:
            validate_temporal_grouping_field(tg.field)
    except ValueError as e:
        raise ModelRetry(f"{str(e)} Use discover_filter_paths to find datetime fields.")

    ctx.deps.state.query = cast(Query, ctx.deps.state.query).model_copy(update={"temporal_group_by": temporal_groups})

    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )

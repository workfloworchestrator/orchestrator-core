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
from ag_ui.core import EventType, StateDeltaEvent, StateSnapshotEvent
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
    build_state_changes_for_aggregation,
    build_state_changes_for_search,
    execute_aggregation_with_persistence,
    execute_search_with_persistence,
)
from orchestrator.search.agent.state import ExportData, SearchState
from orchestrator.search.agent.validation import require_action
from orchestrator.search.aggregations import Aggregation, FieldAggregation, TemporalGrouping
from orchestrator.search.core.types import ActionType, EntityType, FilterOp
from orchestrator.search.filters import FilterTree
from orchestrator.search.query.exceptions import PathNotFoundError, QueryValidationError
from orchestrator.search.query.export import fetch_export_data
from orchestrator.search.query.models import BaseQuery
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
    ctx.deps.state.results_data = None
    ctx.deps.state.export_data = None

    # Set fresh parameters with no filters
    ctx.deps.state.parameters = {
        "action": action,
        "entity_type": entity_type,
        "filters": None,
        "query": final_query,
    }

    logger.debug("New search started", parameters=ctx.deps.state.parameters)

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
    if ctx.deps.state.parameters is None:
        raise ModelRetry("Search parameters are not initialized. Call start_new_search first.")

    entity_type = EntityType(ctx.deps.state.parameters["entity_type"])

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

    filter_data = None if filters is None else filters.model_dump(mode="json", by_alias=True)
    ctx.deps.state.parameters["filters"] = filter_data

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
) -> StateDeltaEvent:
    """Execute a search to find and rank entities.

    Use this tool for SELECT action to find entities matching your criteria.
    For counting or computing statistics, use run_aggregation instead.
    """
    # @require_action decorator guarantees parameters is not None
    params = BaseQuery.create(**cast(dict[str, Any], ctx.deps.state.parameters))
    params.limit = limit

    # Execute with persistence
    search_response, run_id, query_id = await execute_search_with_persistence(params, db.session, ctx.deps.state.run_id)

    # Build state changes
    run_id_existed = ctx.deps.state.run_id is not None
    query_id_existed = ctx.deps.state.query_id is not None

    ctx.deps.state.run_id = run_id
    ctx.deps.state.query_id = query_id
    ctx.deps.state.results_data, changes = build_state_changes_for_search(
        search_response, query_id, run_id, run_id_existed, query_id_existed
    )

    return StateDeltaEvent(type=EventType.STATE_DELTA, delta=changes)


@search_toolset.tool
@require_action(ActionType.COUNT, ActionType.AGGREGATE)
async def run_aggregation(
    ctx: RunContext[StateDeps[SearchState]],
) -> StateDeltaEvent:
    """Execute an aggregation to compute counts or statistics over entities.

    Use this tool for COUNT or AGGREGATE actions after setting up:
    - Grouping fields with set_grouping or set_temporal_grouping
    - Aggregation functions with set_aggregations (for AGGREGATE action)
    """
    # @require_action decorator guarantees parameters is not None
    params = BaseQuery.create(**cast(dict[str, Any], ctx.deps.state.parameters))

    logger.debug(
        "Executing aggregation",
        search_entity_type=params.entity_type.value,
        has_filters=params.filters is not None,
        query=params.query,
        action=params.action,
    )

    aggregation_response, run_id, query_id = await execute_aggregation_with_persistence(
        params, db.session, ctx.deps.state.run_id
    )

    run_id_existed = ctx.deps.state.run_id is not None
    query_id_existed = ctx.deps.state.query_id is not None

    ctx.deps.state.run_id = run_id
    ctx.deps.state.query_id = query_id
    ctx.deps.state.aggregation_data, changes = build_state_changes_for_aggregation(
        aggregation_response, query_id, run_id, run_id_existed, query_id_existed
    )

    return StateDeltaEvent(type=EventType.STATE_DELTA, delta=changes)


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
    if not entity_type and ctx.deps.state.parameters:
        entity_type = EntityType(ctx.deps.state.parameters.get("entity_type"))
    if not entity_type:
        entity_type = EntityType.SUBSCRIPTION

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
        ValueError: If no search results are available.
    """
    if not ctx.deps.state.results_data or not ctx.deps.state.results_data.results:
        raise ValueError("No search results available. Run a search first before fetching entity details.")

    if not ctx.deps.state.parameters:
        raise ValueError("No search parameters found.")

    entity_type = EntityType(ctx.deps.state.parameters["entity_type"])

    entity_ids = [r.entity_id for r in ctx.deps.state.results_data.results[:limit]]

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
) -> StateSnapshotEvent:
    """Prepares export URL using the last executed search query."""
    if not ctx.deps.state.query_id or not ctx.deps.state.run_id:
        raise ValueError("No search has been executed yet. Run a search first before exporting.")

    logger.debug(
        "Prepared query for export",
        query_id=str(ctx.deps.state.query_id),
    )

    download_url = f"{app_settings.BASE_URL}/api/search/queries/{ctx.deps.state.query_id}/export"

    ctx.deps.state.export_data = ExportData(
        query_id=str(ctx.deps.state.query_id),
        download_url=download_url,
        message="Export ready for download.",
    )

    logger.debug("Export data set in state", export_data=ctx.deps.state.export_data.model_dump())

    # Should use StateDelta here? Use snapshot to workaround state persistence issue
    # TODO: Fix root cause; state is empty on frontend when it should have data from run_search
    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )


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

    ctx.deps.state.parameters["group_by"] = group_by_paths  # type: ignore[index]

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

    ctx.deps.state.parameters["aggregations"] = [agg.model_dump() for agg in aggregations]  # type: ignore[index]

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

    ctx.deps.state.parameters["temporal_group_by"] = [tg.model_dump() for tg in temporal_groups]  # type: ignore[index]

    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )

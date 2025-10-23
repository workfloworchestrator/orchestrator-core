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
from typing import Any

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
from orchestrator.db import AgentRunTable, SearchQueryTable, db
from orchestrator.search.agent.json_patch import JSONPatchOp
from orchestrator.search.agent.state import ExportData, SearchResultsData, SearchState
from orchestrator.search.core.types import ActionType, EntityType, FilterOp
from orchestrator.search.export import fetch_export_data
from orchestrator.search.filters import FilterTree
from orchestrator.search.retrieval.engine import execute_search
from orchestrator.search.retrieval.exceptions import FilterValidationError, PathNotFoundError
from orchestrator.search.retrieval.query_state import SearchQueryState
from orchestrator.search.retrieval.validation import validate_filter_tree
from orchestrator.search.schemas.parameters import BaseSearchParameters
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


def _set_parameters(
    ctx: RunContext[StateDeps[SearchState]],
    entity_type: EntityType,
    action: str | ActionType,
    query: str,
    filters: Any | None,
) -> None:
    """Internal helper to set parameters."""
    ctx.deps.state.parameters = {
        "action": action,
        "entity_type": entity_type,
        "filters": filters,
        "query": query,
    }


@search_toolset.tool
async def start_new_search(
    ctx: RunContext[StateDeps[SearchState]],
    entity_type: EntityType,
    action: str | ActionType = ActionType.SELECT,
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
    _set_parameters(ctx, entity_type, action, final_query, None)

    logger.debug("New search started", parameters=ctx.deps.state.parameters)

    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )


@search_toolset.tool(retries=2)
async def set_filter_tree(
    ctx: RunContext[StateDeps[SearchState]],
    filters: FilterTree | None,
) -> StateDeltaEvent:
    """Replace current filters atomically with a full FilterTree, or clear with None.

    Requirements:
    - Root/group operators must be 'AND' or 'OR' (uppercase).
    - Provide either PathFilters or nested groups under `children`.
    - See the FilterTree schema examples for the exact shape.
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
    except FilterValidationError as e:
        # ModelRetry will trigger an agent retry, containing the specific validation error.
        logger.debug(f"Filter validation failed: {str(e)}")
        raise ModelRetry(str(e))
    except Exception as e:
        logger.error("Unexpected Filter validation exception", error=str(e))
        raise ModelRetry(f"Filter validation failed: {str(e)}. Please check your filter structure and try again.")

    filter_data = None if filters is None else filters.model_dump(mode="json", by_alias=True)
    filters_existed = "filters" in ctx.deps.state.parameters
    ctx.deps.state.parameters["filters"] = filter_data
    return StateDeltaEvent(
        type=EventType.STATE_DELTA,
        delta=[
            JSONPatchOp.upsert(
                path="/parameters/filters",
                value=filter_data,
                existed=filters_existed,
            )
        ],
    )


@search_toolset.tool
async def run_search(
    ctx: RunContext[StateDeps[SearchState]],
    limit: int = 10,
) -> StateDeltaEvent:
    """Execute the search with the current parameters and save to database."""
    if not ctx.deps.state.parameters:
        raise ValueError("No search parameters set")

    params = BaseSearchParameters.create(**ctx.deps.state.parameters)
    logger.debug(
        "Executing database search",
        search_entity_type=params.entity_type.value,
        limit=limit,
        has_filters=params.filters is not None,
        query=params.query,
        action=params.action,
    )

    if params.filters:
        logger.debug("Search filters", filters=params.filters)

    params.limit = limit

    changes: list[JSONPatchOp] = []

    if not ctx.deps.state.run_id:
        agent_run = AgentRunTable(agent_type="search")

        db.session.add(agent_run)
        db.session.commit()
        db.session.expire_all()  # Release connection to prevent stacking while agent runs

        ctx.deps.state.run_id = agent_run.run_id
        logger.debug("Created new agent run", run_id=str(agent_run.run_id))
        changes.append(JSONPatchOp(op="add", path="/run_id", value=str(ctx.deps.state.run_id)))

    # Get query with embedding and save to DB
    search_response = await execute_search(params, db.session)
    query_embedding = search_response.query_embedding
    query_state = SearchQueryState(parameters=params, query_embedding=query_embedding)
    query_number = db.session.query(SearchQueryTable).filter_by(run_id=ctx.deps.state.run_id).count() + 1
    search_query = SearchQueryTable.from_state(
        state=query_state,
        run_id=ctx.deps.state.run_id,
        query_number=query_number,
    )
    db.session.add(search_query)
    db.session.commit()
    db.session.expire_all()

    query_id_existed = ctx.deps.state.query_id is not None
    ctx.deps.state.query_id = search_query.query_id
    logger.debug("Saved search query", query_id=str(search_query.query_id), query_number=query_number)
    changes.append(JSONPatchOp.upsert(path="/query_id", value=str(ctx.deps.state.query_id), existed=query_id_existed))

    logger.debug(
        "Search completed",
        total_results=len(search_response.results),
    )

    # Store results data for both frontend display and agent context
    results_url = f"{app_settings.BASE_URL}/api/search/queries/{ctx.deps.state.query_id}"

    results_data_existed = ctx.deps.state.results_data is not None
    ctx.deps.state.results_data = SearchResultsData(
        query_id=str(ctx.deps.state.query_id),
        results_url=results_url,
        total_count=len(search_response.results),
        message=f"Found {len(search_response.results)} results.",
        results=search_response.results,  # Include actual results in state
    )
    changes.append(
        JSONPatchOp.upsert(
            path="/results_data", value=ctx.deps.state.results_data.model_dump(), existed=results_data_existed
        )
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
async def prepare_export(
    ctx: RunContext[StateDeps[SearchState]],
) -> StateSnapshotEvent:
    """Prepares export URL using the last executed search query."""
    if not ctx.deps.state.query_id or not ctx.deps.state.run_id:
        raise ValueError("No search has been executed yet. Run a search first before exporting.")

    if not ctx.deps.state.parameters:
        raise ValueError("No search parameters found. Run a search first before exporting.")

    # Validate that export is only available for SELECT actions
    action = ctx.deps.state.parameters.get("action", ActionType.SELECT)
    if action != ActionType.SELECT:
        raise ValueError(
            f"Export is only available for SELECT actions. Current action is '{action}'. "
            "Please run a SELECT search first."
        )

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

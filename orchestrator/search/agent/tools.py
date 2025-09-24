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

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

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
    search_processes,
    search_products,
    search_subscriptions,
    search_workflows,
)
from orchestrator.schemas.search import SearchResultsSchema
from orchestrator.search.core.types import ActionType, EntityType, FilterOp
from orchestrator.search.filters import FilterTree
from orchestrator.search.retrieval.exceptions import FilterValidationError, PathNotFoundError
from orchestrator.search.retrieval.validation import validate_filter_tree
from orchestrator.search.schemas.parameters import PARAMETER_REGISTRY, BaseSearchParameters

from .state import SearchState

logger = structlog.get_logger(__name__)


P = TypeVar("P", bound=BaseSearchParameters)

SearchFn = Callable[[P], Awaitable[SearchResultsSchema[Any]]]

SEARCH_FN_MAP: dict[EntityType, SearchFn] = {
    EntityType.SUBSCRIPTION: search_subscriptions,
    EntityType.WORKFLOW: search_workflows,
    EntityType.PRODUCT: search_products,
    EntityType.PROCESS: search_processes,
}

search_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=1)


def last_user_message(ctx: RunContext[StateDeps[SearchState]]) -> str | None:
    for msg in reversed(ctx.messages):
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return None


@search_toolset.tool
async def set_search_parameters(
    ctx: RunContext[StateDeps[SearchState]],
    entity_type: EntityType,
    action: str | ActionType = ActionType.SELECT,
) -> StateSnapshotEvent:
    """Sets the initial search context, like the entity type and the user's query.

    This MUST be the first tool called to start any new search.
    Warning: Calling this tool will erase any existing filters and search results from the state.
    """
    params = ctx.deps.state.parameters or {}
    is_new_search = params.get("entity_type") != entity_type.value
    final_query = (last_user_message(ctx) or "") if is_new_search else params.get("query", "")

    logger.debug(
        "Setting search parameters",
        entity_type=entity_type.value,
        action=action,
        is_new_search=is_new_search,
        query=final_query,
    )

    ctx.deps.state.parameters = {"action": action, "entity_type": entity_type, "filters": None, "query": final_query}
    ctx.deps.state.results = []
    logger.debug("Search parameters set", parameters=ctx.deps.state.parameters)

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

    Requirements:
    - Root/group operators must be 'AND' or 'OR' (uppercase).
    - Provide either PathFilters or nested groups under `children`.
    - See the FilterTree schema examples for the exact shape.
    """
    if ctx.deps.state.parameters is None:
        raise ModelRetry("Search parameters are not initialized. Call set_search_parameters first.")

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
    ctx.deps.state.parameters["filters"] = filter_data
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state.model_dump())


@search_toolset.tool
async def execute_search(
    ctx: RunContext[StateDeps[SearchState]],
    limit: int = 10,
) -> StateSnapshotEvent:
    """Execute the search with the current parameters."""
    if not ctx.deps.state.parameters:
        raise ValueError("No search parameters set")

    entity_type = EntityType(ctx.deps.state.parameters["entity_type"])
    param_class = PARAMETER_REGISTRY.get(entity_type)
    if not param_class:
        raise ValueError(f"Unknown entity type: {entity_type}")

    params = param_class(**ctx.deps.state.parameters)
    logger.debug(
        "Executing database search",
        search_entity_type=entity_type.value,
        limit=limit,
        has_filters=params.filters is not None,
        query=params.query,
        action=params.action,
    )

    if params.filters:
        logger.debug("Search filters", filters=params.filters)

    params.limit = limit

    fn = SEARCH_FN_MAP[entity_type]
    search_results = await fn(params)

    logger.debug(
        "Search completed",
        total_results=len(search_results.data) if search_results.data else 0,
    )

    ctx.deps.state.results = search_results.data

    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state.model_dump())


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

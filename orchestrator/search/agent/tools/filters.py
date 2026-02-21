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

from typing import Any, cast

import structlog
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.toolsets import FunctionToolset

from orchestrator.api.api_v1.endpoints.search import (
    get_definitions,
    list_paths,
)
from orchestrator.search.agent.state import SearchState
from orchestrator.search.core.types import EntityType, FilterOp, QueryOperation
from orchestrator.search.filters import FilterTree
from orchestrator.search.query.exceptions import PathNotFoundError, QueryValidationError
from orchestrator.search.query.queries import AggregateQuery, CountQuery, Query, SelectQuery
from orchestrator.search.query.validation import validate_filter_tree

logger = structlog.get_logger(__name__)


def ensure_query_initialized(
    state: SearchState,
    entity_type: EntityType,
    query_operation: QueryOperation = QueryOperation.SELECT,
) -> None:
    """Lazy-initialize query on state if not already set, or re-create if type mismatches.

    Preserves filters (from existing query or pending_filters) when creating/upgrading.
    """
    expected_types = {
        QueryOperation.SELECT: SelectQuery,
        QueryOperation.COUNT: CountQuery,
        QueryOperation.AGGREGATE: AggregateQuery,
    }
    expected_type = expected_types[query_operation]

    if state.query is not None and isinstance(state.query, expected_type):
        return

    if state.query is not None:
        logger.warning(
            "Query type mismatch — re-creating query, grouping/aggregations will be lost",
            existing_type=type(state.query).__name__,
            requested_operation=query_operation.value,
        )

    # Collect filters: from existing query, or from pending_filters set by set_filter_tree
    filters = (state.query.filters if state.query else None) or state.pending_filters

    if query_operation == QueryOperation.SELECT:
        state.query = SelectQuery(entity_type=entity_type, query_text=state.user_input, filters=filters)
    elif query_operation == QueryOperation.COUNT:
        state.query = CountQuery(entity_type=entity_type, filters=filters)
    else:
        state.query = AggregateQuery(entity_type=entity_type, aggregations=[], filters=filters)

    state.pending_filters = None


filter_building_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=2)


@filter_building_toolset.tool
async def set_filter_tree(
    ctx: RunContext[StateDeps[SearchState]],
    filters: FilterTree | None,
    entity_type: EntityType,
) -> FilterTree | None:
    """Replace current filters atomically with a full FilterTree, or clear with None.

    See FilterTree model for structure, operators, and examples.
    Filters are validated immediately and applied when the query executes.
    """
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
        logger.debug(f"Query validation failed: {str(e)}")
        raise ModelRetry(str(e))
    except Exception as e:
        logger.error("Unexpected Filter validation exception", error=str(e))
        raise ModelRetry(f"Filter validation failed: {str(e)}. Please check your filter structure and try again.")

    # Store validated filters — applied when query is created by run_search/run_aggregation
    if ctx.deps.state.query is not None:
        ctx.deps.state.query = cast(Query, ctx.deps.state.query).model_copy(update={"filters": filters})
    else:
        ctx.deps.state.pending_filters = filters

    return filters


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
            raise ModelRetry("Entity type not specified and no query in state. Pass entity_type.")

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

import asyncio
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
    search_processes,
    search_products,
    search_subscriptions,
    search_workflows,
)
from orchestrator.schemas.search import ConnectionSchema
from orchestrator.search.core.types import ActionType, EntityType
from orchestrator.search.filters import FilterTree
from orchestrator.search.retrieval.validation import validate_filter_tree
from orchestrator.search.schemas.parameters import PARAMETER_REGISTRY, BaseSearchParameters

from .state import SearchState

logger = structlog.get_logger(__name__)
P = TypeVar("P", bound=BaseSearchParameters)

SearchFn = Callable[[P], ConnectionSchema[Any]] | Callable[[P], Awaitable[ConnectionSchema[Any]]]

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


@search_toolset.tool  # type: ignore[misc]
async def set_search_parameters(
    ctx: RunContext[StateDeps[SearchState]],
    entity_type: EntityType,
    action: str | ActionType = ActionType.SELECT,
) -> StateSnapshotEvent:
    params = ctx.deps.state.parameters or {}
    is_new_search = params.get("entity_type") != entity_type.value
    final_query = (last_user_message(ctx) or "") if is_new_search else params.get("query", "")

    ctx.deps.state.parameters = {"action": action, "entity_type": entity_type, "filters": None, "query": final_query}
    ctx.deps.state.results = []
    logger.info(f"Set search parameters: entity_type={entity_type}, action={action}")

    return StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT,
        snapshot=ctx.deps.state.model_dump(),
    )


@search_toolset.tool(retries=2)  # type: ignore[misc]
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

    try:
        await validate_filter_tree(filters, entity_type)
    except Exception as e:
        raise ModelRetry(str(e))

    ctx.deps.state.parameters["filters"] = None if filters is None else filters.model_dump(mode="json", by_alias=True)
    logger.info(
        "Set filter tree",
        filters=None if filters is None else filters.model_dump(mode="json", by_alias=True),
    )
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state.model_dump())


@search_toolset.tool  # type: ignore[misc]
async def execute_search(
    ctx: RunContext[StateDeps[SearchState]],
    limit: int = 5,
) -> StateSnapshotEvent:
    """Execute the search with the current parameters."""
    if not ctx.deps.state.parameters:
        raise ValueError("No search parameters set")

    entity_type = EntityType(ctx.deps.state.parameters["entity_type"])
    param_class = PARAMETER_REGISTRY.get(entity_type)
    if not param_class:
        raise ValueError(f"Unknown entity type: {entity_type}")

    params = param_class(**ctx.deps.state.parameters)
    logger.info("Executing database search", **params.model_dump(mode="json"))

    fn = SEARCH_FN_MAP[entity_type]
    page_connection = await fn(params) if asyncio.iscoroutinefunction(fn) else fn(params)
    ctx.deps.state.results = [item.model_dump(mode="json") for item in page_connection.page[:limit]]

    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state.model_dump())

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

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, Optional, TypeVar

import structlog
from ag_ui.core import EventType, StateSnapshotEvent
from langfuse import observe
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.toolsets import FunctionToolset

from llm_guard import scan_prompt
from llm_guard.model import Model
from llm_guard.input_scanners import PromptInjection, Toxicity

from orchestrator.api.api_v1.endpoints.search import (
    get_definitions,
    list_paths,
    search_processes,
    search_products,
    search_subscriptions,
    search_workflows,
)
from orchestrator.schemas.search import SearchResultsSchema, SubscriptionSearchResult
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



# python
from typing import Any, Dict, Optional

class PipelineOutputAdapter:
    """
    Wraps a pipeline callable and adapts outputs by:
      - remapping labels via `label_map`
      - forcing a specific label via `force_label`
      - adding a constant `score_offset` (optionally clamped to [0, 1])
    """
    def __init__(
        self,
        base_pipeline,
        label_map: Optional[Dict[str, str]] = None,
        force_label: Optional[str] = None,
        clamp_to_unit: bool = True,
    ):
        self._base = base_pipeline
        self._label_map = dict(label_map) if label_map else None
        self._force_label = force_label
        self._clamp = bool(clamp_to_unit)

    def __call__(self, *args, **kwargs):
        result = self._base(*args, **kwargs)
        return self._adapt(result)

    def _adapt(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return self._adapt_dict(obj)
        if isinstance(obj, list):
            return [self._adapt(x) for x in obj]
        return obj

    def _adapt_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(d)
        logger.debug("Adapting output", out=out)
        # Force or remap label
        if self._force_label is not None:
            if out["label"] == "jailbreak":
                out["label"] = self._force_label
        elif self._label_map and isinstance(out.get("label"), str):
            out["label"] = self._label_map.get(out["label"], out["label"])

        return out


def attach_pipeline_adapter(
    scanner: Any,
    *,
    label_map: Optional[Dict[str, str]] = None,
    force_label: Optional[str] = "INJECTION",
    clamp_to_unit: bool = False,
) -> bool:
    """
    Attempts to wrap the scanner's underlying pipeline-like callable.
    Returns True if successfully attached, else False.
    Tries common attribute names used for HF pipelines.
    """
    candidates = ("pipeline", "_pipeline", "pipe", "classifier", "_classifier")
    for name in candidates:
        base = getattr(scanner, name, None)
        if callable(base):
            setattr(
                scanner,
                name,
                PipelineOutputAdapter(
                    base,
                    label_map=label_map,
                    force_label=force_label,
                    clamp_to_unit=clamp_to_unit,
                ),
            )
            return True
    return False


# Usage example with your snippet:

model = Model(
    path="qualifire/prompt-injection-sentinel",
    pipeline_kwargs={
        "return_token_type_ids": False,
        "max_length": 512,
        "truncation": True,
    },
)

# Create the scanner as usual
prompt_scanner = PromptInjection(model=model)

# Inject the adapter so scoring sees label='INJECTION' and score+1.0
# clamp_to_unit=False allows scores > 1.0 before rounding in your scorer
attached = attach_pipeline_adapter(
    prompt_scanner,
    force_label="INJECTION",
)

# Use the adapted scanner
input_scanners = [prompt_scanner]

def last_user_message(ctx: RunContext[StateDeps[SearchState]]) -> str | None:
    for msg in reversed(ctx.messages):
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return None


@search_toolset.tool
@observe(name="agent_endpoint")
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
@observe(name="agent_endpoint")
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
@observe(name="agent_endpoint")
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
    #scan_search_results(search_results.data)

    ctx.deps.state.results = search_results.data

    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state.model_dump())


@observe(name="agent_scan_content")
def scan_search_results(data):
    """Scan search results for each subscription and return on first invalid result"""
    for result in data:
        if not isinstance(result, SubscriptionSearchResult):
            continue

        # Scan each value in the subscription dictionary
        for field_key, field_value in result.subscription.items():
            logger.debug("Processing subscription field", field_key=field_key)

            prompt, valid, scan_results = scan_dict_recursive(field_value)

            # Debug logging for each scan
            logger.debug("Scan results",
                         field_key=field_key,
                         prompt=prompt,
                         valid=valid,
                         scan_results=scan_results)

            # Check if valid is a dictionary (from scan_prompt) and any scanner failed
            if prompt is not None and scan_results is not None:
                is_invalid = False
                if isinstance(valid, dict):
                    # Check if any scanner returned False
                    is_invalid = any(not v for v in valid.values())
                else:
                    # Fallback for boolean valid
                    is_invalid = not valid

                if is_invalid:
                    logger.info("Found invalid content, returning scan results",
                                field_key=field_key,
                                prompt=prompt[:100] if prompt else None,
                                valid_results=valid)
                    return prompt, scan_results

    logger.debug("All scan results valid or no string content found")
    return None, None


@observe(name="agent_scan_instance")
def scan_dict_recursive(value):
    """Recursively scan dictionary values for string content"""
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            logger.debug("Scanning nested dict item", item_key=item_key)
            prompt, valid, scan_results = scan_dict_recursive(item_value)

            # Check if we got a result and if it's invalid
            if prompt is not None and scan_results is not None:
                is_invalid = False
                if isinstance(valid, dict):
                    # Check if any scanner returned False
                    is_invalid = any(not v for v in valid.values())
                else:
                    # Fallback for boolean valid
                    is_invalid = not valid

                if is_invalid:
                    return prompt, valid, scan_results

        # If we get here, all nested items were valid or not strings
        return None, True, None

    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            logger.debug("Scanning list item", index=i)
            prompt, valid, scan_results = scan_dict_recursive(item)

            # Check if we got a result and if it's invalid
            if prompt is not None and scan_results is not None:
                is_invalid = False
                if isinstance(valid, dict):
                    # Check if any scanner returned False
                    is_invalid = any(not v for v in valid.values())
                else:
                    # Fallback for boolean valid
                    is_invalid = not valid

                if is_invalid:
                    return prompt, valid, scan_results

        # If we get here, all list items were valid or not strings
        return None, True, None

    # If it's not a string, skip scanning
    if not isinstance(value, str):
        return None, True, None

    logger.debug("Scanning string value", value_length=len(value))

    # Scan the string prompt
    prompt, valid, scan_results = scan_prompt(
        scanners=input_scanners,
        prompt=str(value),
    )

    logger.debug("String scan completed",
                 prompt_length=len(prompt) if prompt else 0,
                 valid=valid,
                 has_scan_results=scan_results is not None)

    return prompt, valid, scan_results


@search_toolset.tool
@observe(name="agent_endpoint")
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
@observe(name="agent_endpoint")
async def get_valid_operators() -> dict[str, list[FilterOp]]:
    """Gets the mapping of field types to their valid filter operators."""
    definitions = await get_definitions()

    operator_map = {}
    for ui_type, type_def in definitions.items():
        key = ui_type.value

        if hasattr(type_def, "operators"):
            operator_map[key] = type_def.operators
    return operator_map
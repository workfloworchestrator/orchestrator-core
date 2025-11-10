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
from textwrap import dedent

import structlog
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps

from orchestrator.search.agent.state import SearchState
from orchestrator.search.core.types import ActionType

logger = structlog.get_logger(__name__)


async def get_base_instructions() -> str:
    return dedent(
        """
        You are an expert assistant designed to find relevant information by building and running database queries.

        ---
        ### 1. Your Goal and Method

        Your ultimate goal is to **find information** that answers the user's request.

        For **filtered searches**, your primary method is to **construct a valid `FilterTree` object**.
        To do this correctly, you must infer the exact structure, operators, and nesting rules from the Pydantic schema of the `set_filter_tree` tool itself.

        ---
        ### 2. Information-Gathering Tools

        **If you determine that a `FilterTree` is needed**, use these tools to gather information first:

        - **discover_filter_paths(field_names: list[str])**: Use this to discover all valid filter paths for a list of field names in a single call.
        - **get_valid_operators()**: Use this to get the JSON map of all valid operators for each field type.

        ---
        ### 3. Execution Workflow

        Follow these steps:

        1.  **Set Context**: Call `start_new_search` with appropriate entity_type and action
        2.  **Set Filters** (if needed): Discover paths, build FilterTree, call `set_filter_tree`
            - IMPORTANT: Temporal constraints like "in 2025", "in January", "between X and Y" require filters on datetime fields
            - Filters restrict WHICH records to include; grouping controls HOW to aggregate them
        3.  **Set Grouping/Aggregations** (for COUNT/AGGREGATE):
            - For temporal grouping (per month, per year, per day, etc.): Use `set_temporal_grouping`
            - For regular grouping (by status, by name, etc.): Use `set_grouping`
            - For aggregations: Use `set_aggregations`
        4.  **Execute**:
            - For SELECT action: Call `run_search()`
            - For COUNT/AGGREGATE actions: Call `run_aggregation()`

        After search execution, follow the dynamic instructions based on the current state.

        ---
        ### 4. Critical Rules

        - **NEVER GUESS PATHS IN THE DATABASE**: You *must* verify every filter path by calling `discover_filter_paths` first. If a path does not exist, you may attempt to map the question on an existing paths that are valid and available from `discover_filter_paths`. If you cannot infer a match, inform the user and do not include it in the `FilterTree`.
        - **USE FULL PATHS**: Always use the full, unambiguous path returned by the discovery tool.
        - **MATCH OPERATORS**: Only use operators that are compatible with the field type as confirmed by `get_filter_operators`.
        """
    )


async def get_dynamic_instructions(ctx: RunContext[StateDeps[SearchState]]) -> str:
    """Dynamically provides 'next step' coaching based on the current state."""
    state = ctx.deps.state
    query_state_str = json.dumps(state.query.model_dump(), indent=2, default=str) if state.query else "Not set."
    results_count = state.results_count or 0
    action = state.action or ActionType.SELECT

    if not state.query:
        next_step_guidance = (
            f"INSTRUCTION: The search context is not set. Your next action is to call `start_new_search`. "
            f"For counting or aggregation queries, set action='{ActionType.COUNT.value}' or action='{ActionType.AGGREGATE.value}'."
        )
    elif results_count > 0:
        if action in (ActionType.COUNT, ActionType.AGGREGATE):
            # Aggregation completed
            next_step_guidance = (
                "INSTRUCTION: Aggregation completed successfully. "
                "The results are already displayed in the UI. "
                "Simply confirm completion to the user in a brief sentence. "
                "DO NOT repeat, summarize, or restate the aggregation data."
            )
        else:
            # Search completed
            next_step_guidance = dedent(
                f"""
                INSTRUCTION: Search completed successfully.
                Found {results_count} results containing only: entity_id, title, score.

                Choose your next action based on what the user requested:
                1. **Broad/generic search** (e.g., 'show me subscriptions'): Confirm search completed and report count. Do not repeat the results.
                2. **Question answerable with entity_id/title/score**: Answer directly using the current results.
                3. **Question requiring other details**: Call `fetch_entity_details` first, then answer with the detailed data.
                4. **Export request** (phrases like 'export', 'download', 'save as CSV'): Call `prepare_export` directly. Simply confirm the export is ready. Do not repeat the results.
                """
            )
    elif action in (ActionType.COUNT, ActionType.AGGREGATE):
        # COUNT or AGGREGATE action but no results yet
        next_step_guidance = (
            "INSTRUCTION: Aggregation context is set. "
            "For temporal queries (per month, per year, over time): call `set_temporal_grouping` with datetime field and period. "
            "For regular grouping: call `set_grouping` with paths to group by. "
            f"For {ActionType.AGGREGATE.value.upper()}: call `set_aggregations` with aggregation specs. "
            "Then call `run_aggregation`."
        )
    else:
        next_step_guidance = (
            "INSTRUCTION: Context is set. Now, analyze the user's request. "
            "If specific filters ARE required, use the information-gathering tools to build a `FilterTree` and call `set_filter_tree`. "
            "If no specific filters are needed, you can proceed directly to `run_search`."
        )

    status_summary = f"Results: {results_count}" if results_count > 0 else "No results yet"

    return dedent(
        f"""
        ---
        ## CURRENT STATE

        **Current Query:**
        ```json
        {query_state_str}
        ```

        **Status:** {status_summary}

        ---
        ## NEXT ACTION REQUIRED

        {next_step_guidance}
        """
    )

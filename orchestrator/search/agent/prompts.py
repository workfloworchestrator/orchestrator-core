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

logger = structlog.get_logger(__name__)


async def get_base_instructions() -> str:
    return dedent(
        """
        You are an expert assistant designed to find relevant information by building and running database queries.

        ---
        ### 1. Your Goal and Method

        Your ultimate goal is to **find information** that answers the user's request.

        To do this, you will perform either a broad search or a filtered search.
        For **filtered searches**, your primary method is to **construct a valid `FilterTree` object**.
        To do this correctly, you must infer the exact structure, operators, and nesting rules from the Pydantic schema of the `set_filter_tree` tool itself.

        ---
        ### 2. Information-Gathering Tools

        **If you determine that a `FilterTree` is needed**, use these tools to gather information first:

        - **discover_filter_paths(field_names: list[str])**: Use this to discover all valid filter paths for a list of field names in a single call.
        - **get_valid_operators()**: Use this to get the JSON map of all valid operators for each field type.

        ---
        ### 3. Execution Workflow

        Follow these steps in strict order:

        1.  **Set Context**: If the user is asking for a NEW search, call `start_new_search`.
        2.  **Analyze for Filters**: Based on the user's request, decide if specific filters are necessary.
            - **If filters ARE required**, follow these sub-steps:
                a. **Gather Intel**: Identify all needed field names, then call `discover_filter_paths` and `get_valid_operators` **once each** to get all required information.
                b. **Construct FilterTree**: Build the `FilterTree` object.
                c. **Set Filters**: Call `set_filter_tree`.
        3.  **Execute**: Call `run_search`. This is done for both filtered and non-filtered searches.

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
    param_state_str = json.dumps(state.parameters, indent=2, default=str) if state.parameters else "Not set."
    results_count = state.results_data.total_count if state.results_data else 0

    if state.export_data:
        next_step_guidance = (
            "INSTRUCTION: Export has been prepared successfully. "
            "Simply confirm to the user that the export is ready for download. "
            "DO NOT include or mention the download URL - the UI will display it automatically."
        )
    elif not state.parameters or not state.parameters.get("entity_type"):
        next_step_guidance = (
            "INSTRUCTION: The search context is not set. Your next action is to call `start_new_search`."
        )
    elif results_count > 0:
        next_step_guidance = dedent(
            f"""
            INSTRUCTION: Search completed successfully.
            Found {results_count} results containing only: entity_id, title, score.

            Choose your next action based on what the user requested:
            1. **Broad/generic search** (e.g., 'show me subscriptions'): Confirm search completed and report count. Do nothing else.
            2. **Question answerable with entity_id/title/score**: Answer directly using the current results.
            3. **Question requiring other details**: Call `fetch_entity_details` first, then answer with the detailed data.
            4. **Export request** (phrases like 'export', 'download', 'save as CSV'): Call `prepare_export` directly.
            """
        )
    else:
        next_step_guidance = (
            "INSTRUCTION: Context is set. Now, analyze the user's request. "
            "If specific filters ARE required, use the information-gathering tools to build a `FilterTree` and call `set_filter_tree`. "
            "If no specific filters are needed, you can proceed directly to `run_search`."
        )

    return dedent(
        f"""
        ---
        ## CURRENT STATE

        **Current Search Parameters:**
        ```json
        {param_state_str}
        ```

        **Current Results Count:** {results_count}

        ---
        ## NEXT ACTION REQUIRED

        {next_step_guidance}
        """
    )

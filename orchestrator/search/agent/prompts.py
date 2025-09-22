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

        1.  **Set Context**: Always begin by calling `set_search_parameters`.
        2.  **Analyze for Filters**: Based on the user's request, decide if specific filters are necessary.
            - **If filters ARE required**, follow these sub-steps:
                a. **Gather Intel**: Identify all needed field names, then call `discover_filter_paths` and `get_valid_operators` **once each** to get all required information.
                b. **Construct FilterTree**: Build the `FilterTree` object.
                c. **Set Filters**: Call `set_filter_tree`.
        3.  **Execute**: Call `execute_search`. This is done for both filtered and non-filtered searches.
        4.  **Report**: Answer the users' question directly and summarize when appropiate.

        ---
        ### 4. Critical Rules

        - **NEVER GUESS PATHS**: You *must* verify every filter path by calling `discover_filter_paths` first. If a path does not exist, you must inform the user and not include it in the `FilterTree`.
        - **USE FULL PATHS**: Always use the full, unambiguous path returned by the discovery tool.
        - **MATCH OPERATORS**: Only use operators that are compatible with the field type as confirmed by `get_filter_operators`.
        """
    )


async def get_dynamic_instructions(ctx: RunContext[StateDeps[SearchState]]) -> str:
    """Dynamically provides 'next step' coaching based on the current state."""
    state = ctx.deps.state
    param_state_str = json.dumps(state.parameters, indent=2, default=str) if state.parameters else "Not set."

    next_step_guidance = ""
    if not state.parameters or not state.parameters.get("entity_type"):
        next_step_guidance = (
            "INSTRUCTION: The search context is not set. Your next action is to call `set_search_parameters`."
        )
    else:
        next_step_guidance = (
            "INSTRUCTION: Context is set. Now, analyze the user's request. "
            "If specific filters ARE required, use the information-gathering tools to build a `FilterTree` and call `set_filter_tree`. "
            "If no specific filters are needed, you can proceed directly to `execute_search`."
        )
    return dedent(
        f"""
        ---
        ### Current State & Next Action

        **Current Search Parameters:**
        ```json
        {param_state_str}
        ```

        **{next_step_guidance}**
        """
    )

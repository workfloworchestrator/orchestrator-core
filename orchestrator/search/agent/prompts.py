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


from textwrap import dedent

from orchestrator.search.agent.state import SearchState
from orchestrator.search.core.types import ActionType


def get_query_analysis_prompt(state: SearchState) -> str:
    """Get prompt for QueryAnalysisNode to analyze user intent.

    Args:
        state: Current search state including user_input and existing query (if any)

    Returns:
        Formatted prompt instructing the agent to determine if this is a new search or follow-up
    """
    user_input = state.user_input
    has_existing_query = state.query is not None

    if has_existing_query:
        return dedent(
            f"""
            User message: "{user_input}"

            You have an existing search query already in progress.

            Analyze the user's message and choose the appropriate action:

            **If this is a NEW search request** (user wants to search for something different):
            - Call `start_new_search` with appropriate entity_type and action
            - entity_type: SUBSCRIPTION | PRODUCT | WORKFLOW | PROCESS
            - action: {ActionType.SELECT.value} (listing) | {ActionType.COUNT.value} (counting) | {ActionType.AGGREGATE.value} (numeric operations)

            **If this is a FOLLOW-UP request** (user wants more details/export on current results):
            - Call `fetch_entity_details()` to get more information about current search results
            - Call `prepare_export()` if user wants to export/download results
            - Or other appropriate follow-up tools

            IMPORTANT: Call the appropriate tool immediately without explanatory text.
            """
        ).strip()
    else:
        # First turn: simple new search
        return dedent(
            f"""
            Call `start_new_search` with appropriate entity_type and action for: "{user_input}"

            entity_type: SUBSCRIPTION | PRODUCT | WORKFLOW | PROCESS
            action: {ActionType.SELECT.value} (listing) | {ActionType.COUNT.value} (counting) | {ActionType.AGGREGATE.value} (numeric operations)

            IMPORTANT: Call the tool immediately without any explanatory text.
            """
        ).strip()


def get_filter_building_prompt(state: SearchState) -> str:
    """Get prompt for FilterBuildingNode to build filter trees.

    Args:
        state: Current search state with query information

    Returns:
        Formatted prompt with instructions for building filters
    """
    query_text = state.query.query_text if state.query and hasattr(state.query, "query_text") else "None"

    return dedent(
        f"""
        Query: "{query_text}"

        If specific filters needed (e.g., "active", "in 2025"):
        1. Call `discover_filter_paths` to find valid paths
        2. Call `get_valid_operators` for compatible operators
        3. Build FilterTree and call `set_filter_tree(filters=...)`

        If NO specific filters needed (generic queries):
        - Call `set_filter_tree(filters=None)`

        Never guess paths. Temporal constraints like "in 2025" require datetime filters.
        After calling the tools, briefly confirm what you did.
        """
    ).strip()


def get_execution_prompt(state: SearchState) -> str:
    """Get prompt for ExecutionNode to execute search or aggregation.

    Args:
        state: Current search state with action and query information

    Returns:
        Formatted prompt with instructions for execution
    """
    action = state.action

    if action == ActionType.SELECT:
        return "Call `run_search()` to execute the search. Briefly confirm after calling."

    elif action in (ActionType.COUNT, ActionType.AGGREGATE):
        return dedent(
            f"""
            Action: {action.value}

            Set up grouping if needed:
            - Temporal: `set_temporal_grouping()`
            - Regular: `set_grouping()`
            - Aggregations (for AGGREGATE only, not COUNT): `set_aggregations()`

            Then call `run_aggregation(visualization_type=...)` and confirm.
            """
        ).strip()

    else:
        return "Unknown action type. Cannot execute."


def get_response_prompt(state: SearchState) -> str:
    """Get prompt for ResponseNode to generate final response.

    Args:
        state: Current search state with results

    Returns:
        Formatted prompt with instructions for response generation
    """
    results_count = state.results_count or 0
    action = state.action or ActionType.SELECT

    if action in (ActionType.COUNT, ActionType.AGGREGATE):
        return dedent(
            f"""
            Aggregation completed with {results_count} result groups.

            The results are displayed in the UI visualization.
            Confirm completion briefly - do NOT repeat the data.
            """
        ).strip()

    else:
        # SELECT action
        return dedent(
            f"""
            Search completed. Found {results_count} results (entity_id, title, score).

            Based on the user's request:
            - Generic search: Confirm completion and count (results already shown in UI)
            - Specific question: Answer using current results or call `fetch_entity_details(entity_ids=[...])` if needed
            - Export request: Call `prepare_export()` and confirm

            Keep response concise. Don't repeat data visible in the UI.
            """
        ).strip()

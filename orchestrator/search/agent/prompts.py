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

from orchestrator.search.agent.state import SearchState


def get_intent_prompt() -> str:
    """Get system prompt for IntentNode agent to classify user requests."""
    return (
        "You classify user requests into intents:\n"
        "- SEARCH: Find/list entities without specific filters\n"
        "- SEARCH_WITH_FILTERS: Find entities with conditions (status, dates, etc.)\n"
        "- AGGREGATION: Count/stats without filters\n"
        "- AGGREGATION_WITH_FILTERS: Count/stats with conditions\n"
        "- TEXT_RESPONSE: General questions, greetings, out-of-scope\n\n"
        "Return ONLY the intent enum value."
    )


def get_query_init_prompt() -> str:
    """Get system prompt for query initialization agent."""
    return (
        "You initialize database searches by calling start_new_search.\n\n"
        "entity_type options: SUBSCRIPTION | PRODUCT | WORKFLOW | PROCESS\n"
        "action options:\n"
        "- SELECT: For finding/listing entities\n"
        "- COUNT: For counting operations (e.g., 'how many', 'count by status', 'per month')\n"
        "- AGGREGATE: For numeric operations on fields (SUM, AVG, MIN, MAX)\n\n"
        "Call the tool once, then respond 'Done.'"
    )


def get_filter_building_prompt(state: SearchState) -> str:
    """Get prompt for FilterBuildingNode agent.

    Args:
        state: Current search state with user input and query info

    Returns:
        Complete prompt with instructions and user context
    """
    return (
        "Build database query filters based on the user's request.\n\n"
        "Instructions:\n"
        "1. If specific filters are needed (e.g., 'active', 'in 2025'):\n"
        "   - Call discover_filter_paths to find valid paths\n"
        "   - Call get_valid_operators for compatible operators\n"
        "   - Build FilterTree and call set_filter_tree(filters=...)\n"
        "2. If NO specific filters needed (generic queries):\n"
        "   - Call set_filter_tree(filters=None)\n\n"
        "Rules:\n"
        "- Never guess paths - always verify with discover_filter_paths\n"
        "- Temporal constraints like 'in 2025' require datetime filters\n"
        "- After calling tools, briefly confirm what you did\n\n"
        f"User request: {state.user_input}"
    )


def get_search_execution_prompt(state: SearchState) -> str:
    """Get prompt for SearchNode agent.

    Args:
        state: Current search state

    Returns:
        Complete prompt for executing search
    """
    return (
        "Execute the database search by calling run_search().\n"
        "After calling the tool, respond with 'Done.'\n\n"
        f"User request: {state.user_input}"
    )


def get_aggregation_execution_prompt(state: SearchState) -> str:
    """Get prompt for AggregationNode agent.

    Args:
        state: Current search state with action and query info

    Returns:
        Complete prompt for executing aggregation
    """
    action = state.action.value if state.action else "unknown"

    return (
        f"Execute the aggregation query (action: {action}).\n\n"
        "Instructions:\n"
        "1. Set up grouping if needed:\n"
        "   - For temporal: call set_temporal_grouping()\n"
        "   - For regular: call set_grouping()\n"
        "2. For AGGREGATE action ONLY (not COUNT):\n"
        "   - Call set_aggregations() to specify what to compute\n"
        "3. Call run_aggregation(visualization_type=...) and respond 'Done.'\n\n"
        f"User request: {state.user_input}"
    )


def get_text_response_prompt(state: SearchState) -> str:
    """Get prompt for TextResponseNode agent.

    Args:
        state: Current search state

    Returns:
        Complete prompt for generating text response
    """
    results_count = state.results_count or 0
    action = state.action

    if action and action.value in ["count", "aggregate"]:
        return (
            f"Aggregation completed with {results_count} result groups.\n\n"
            "The results are displayed in the UI visualization.\n"
            "Provide a brief confirmation - do NOT repeat the data.\n\n"
            f"User request: {state.user_input}"
        )
    else:
        return (
            "Generate a helpful response to the user's question.\n\n"
            f"User request: {state.user_input}\n"
            f"Search results found: {results_count}\n\n"
            "Instructions:\n"
            "- If results_count is 0: Tell user nothing was found\n"
            "- If results exist: Briefly confirm what was found\n"
            "- Keep response concise\n"
            "- Results are already displayed in the UI - don't repeat them"
        )

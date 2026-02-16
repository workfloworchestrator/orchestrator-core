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

from orchestrator.search.agent import tools
from orchestrator.search.agent.state import SearchState
from orchestrator.search.core.types import EntityType

GRAPH_CONTEXT = """You are an agent in a cyclic graph that can visit nodes multiple times per request.
When tools complete successfully, results are immediately streamed to the user's UI in real-time."""

FILTERING_RULES = f"""### Filtering Rules (if query requires filters)
- Temporal constraints like "in 2025", "between X and Y" require filters on datetime fields
- **NEVER GUESS PATHS IN THE DATABASE**: You *must* verify every filter path by calling `{tools.discover_filter_paths.__name__}` first
- **START WITH SIMPLE NAMES**: For "active subscriptions", try "status" first, not "subscription.status" or variations
- Common filter examples: "status", "name", "description", "start_date", "end_date", "customer_id"
- If a path does not exist, you may attempt to map the question to existing paths that are valid
- **USE FULL PATHS**: Always use the full, unambiguous path returned by the discovery tool
- **MATCH OPERATORS**: Only use operators compatible with the field type as confirmed by `{tools.get_valid_operators.__name__}`"""


def get_search_execution_prompt(state: SearchState) -> str:
    """Get prompt for SearchNode agent.

    Args:
        state: Current search state

    Returns:
        Complete prompt for executing search with optional filtering
    """
    context = state.environment.format_context_for_llm(state)

    return dedent(
        f"""
        # Searching

        {GRAPH_CONTEXT}

        ## Your Task
        Execute a database search to answer the user's request.
        **IMPORTANT**: This query starts empty - previous query filters shown in history are NOT applied unless you rebuild them.

        ## Steps
        1. Determine the entity_type for this search (SUBSCRIPTION, PRODUCT, WORKFLOW, or PROCESS)
        2. If filters needed: Call {tools.discover_filter_paths.__name__}(field_names=[...], entity_type=...), {tools.get_valid_operators.__name__}, build FilterTree, call {tools.set_filter_tree.__name__}
        3. Call {tools.run_search.__name__}(entity_type=...) — you MUST pass entity_type
        4. Explain what you did in 1-2 sentences at most. DO NOT list the actual results, they are already shown to the user.

        {FILTERING_RULES}

        ---

        {context}
    """
    ).strip()


def get_aggregation_execution_prompt(state: SearchState) -> str:
    """Get prompt for AggregationNode agent.

    Args:
        state: Current search state with query_operation and query info

    Returns:
        Complete prompt for executing aggregation with optional filtering and grouping
    """

    context = state.environment.format_context_for_llm(state)

    return dedent(
        f"""
        # Aggregating

        {GRAPH_CONTEXT}

        ## Your Task
        Execute an aggregation query for the user's request.
        **IMPORTANT**: This query starts empty - previous query filters/grouping shown in history are NOT applied unless you rebuild them.

        ## Steps
        1. Determine entity_type (SUBSCRIPTION, PRODUCT, WORKFLOW, or PROCESS) and query_operation (COUNT for counting, AGGREGATE for numeric calculations like SUM/AVG/MIN/MAX)
        2. If filters needed: Call {tools.discover_filter_paths.__name__}(field_names=[...], entity_type=...), {tools.get_valid_operators.__name__}, build FilterTree, call {tools.set_filter_tree.__name__}
        3. Set grouping: Temporal ({tools.set_temporal_grouping.__name__}) or regular ({tools.set_grouping.__name__}) — you MUST pass entity_type and query_operation
        4. For AGGREGATE operation ONLY: Call {tools.set_aggregations.__name__}(entity_type=..., query_operation=...). For COUNT: Do NOT call (counting is automatic)
        5. Call {tools.run_aggregation.__name__}(entity_type=..., query_operation=..., visualization_type=...)
        6. Explain what you did in 1-2 sentences at most. DO NOT list the actual results, they are already shown to the user

        {FILTERING_RULES}
        - Filters restrict WHICH records; grouping controls HOW to aggregate

        ---

        {context}
    """
    ).strip()


def get_text_response_prompt(state: SearchState) -> str:
    """Get prompt for TextResponseNode agent.

    Args:
        state: Current search state

    Returns:
        Complete prompt for generating text response
    """
    context = state.environment.format_context_for_llm(state)
    entity_types = ", ".join([et.value for et in EntityType])

    return dedent(
        f"""
        # Responding

        {GRAPH_CONTEXT}

        ## Available Capabilities
        - Search for entities: {entity_types}
        - Filter searches by various criteria (status, dates, custom fields)
        - Count and aggregate data (totals, averages, grouping by fields or time periods)
        - Return structured data with visualization hints (table, bar chart, line chart, etc.)
        - Export search results
        - Fetch detailed information about specific entities

        ## Your Task
        Generate a helpful response to the user's question.

        ---

        {context}
    """
    ).strip()


def get_planning_prompt(state: SearchState, is_replanning: bool = False) -> str:
    """Get prompt for PlannerNode to create execution plan.

    Args:
        state: Current search state
        is_replanning: True if replanning after a failed execution

    Returns:
        Complete prompt for creating multi-step execution plan
    """
    # Get context for replanning (NOT conversation - that's in message_history now)
    context = state.environment.format_context_for_llm(
        state,
        include_current_run_steps=is_replanning,
    )

    # Different guidelines for initial planning vs replanning
    if is_replanning:
        guidelines = """## Your Task & Guidelines
        Replan after failure - analyze what went wrong and create a new approach.

        1. **Review what failed**: Check "Steps already executed" to see what went wrong
        2. **Adjust approach**: Create a different plan that avoids the previous failure
        3. **Use available context**: If results exist from before the failure, you can use them
        4. **Keep it simple**: Prefer 1-2 tasks when possible"""
    else:
        guidelines = """## Your Task & Guidelines
        Analyze the user's request and create a sequential execution plan.

        1. **Check available context**: If results already exist from previous turns, you can act on them directly
        2. **Break into tasks**: Each task = one node execution. Create as many tasks as needed to fulfill the request.

        ## Example
        Request: "Find X and export them"
        Plan: {{"tasks": [{{"action_type": "search", "reasoning": "Search for X"}}, {{"action_type": "result_actions", "reasoning": "Export the results"}}]}}

        Note: Exports or detailed entity data require a RESULT_ACTIONS task."""

    return dedent(
        f"""
        # Execution Planning

        {GRAPH_CONTEXT}

        {guidelines}

        IMPORTANT: Query execution nodes automatically stream results to the user.
        Do NOT create redundant tasks just to "show" or "present" results that are already displayed.

        ---

        {context}
        """
    ).strip()


def get_result_actions_prompt(state: SearchState) -> str:
    """Get prompt for ResultActionsNode agent.

    Args:
        state: Current search state with environment and user input

    Returns:
        Complete prompt for result actions
    """
    context = state.environment.format_context_for_llm(state)
    return dedent(
        f"""
        # Acting on Results

        {GRAPH_CONTEXT}

        Act on existing search/aggregation results.

        ## Available Actions
        - If user wants to EXPORT/DOWNLOAD results: Call {tools.prepare_export.__name__}() ONLY
        - If user wants DETAILED INFORMATION about entities: Call {tools.fetch_entity_details.__name__}(limit=...)

        ## Your Task
        Execute the requested action. After calling the tool, respond with a single short confirmation like "Prepared an export for [description]." or "Fetched details for [count] entities."

        IMPORTANT: For export requests, ONLY call prepare_export(). Do NOT fetch entity details.
        ---

        {context}
        """
    ).strip()

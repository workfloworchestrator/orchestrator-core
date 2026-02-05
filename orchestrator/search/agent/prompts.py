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
from orchestrator.search.agent.state import IntentType, SearchState
from orchestrator.search.core.types import EntityType


def get_search_execution_prompt(state: SearchState) -> str:
    """Get prompt for SearchNode agent.

    Args:
        state: Current search state

    Returns:
        Complete prompt for executing search with optional filtering
    """
    env = state.environment
    conversation = env.format_for_llm(max_turns=3)

    return dedent(
        f"""
        ## Recent Conversation
        {conversation}

        ## Current Request
        "{state.user_input}"

        ---

        You are an expert assistant designed to find relevant information by building and running database queries.

        ### Your Task
        Execute a database search to answer the user's request.

        ### Filtering Rules (if query requires filters)
        - **NEVER GUESS PATHS IN THE DATABASE**: You *must* verify every filter path by calling `{tools.discover_filter_paths.__name__}` first
        - **START WITH SIMPLE NAMES**: For "active subscriptions", try "status" first, not "subscription.status" or variations
        - Common filter examples: "status", "name", "description", "start_date", "end_date", "customer_id"
        - If a path does not exist, you may attempt to map the question to existing paths that are valid
        - **USE FULL PATHS**: Always use the full, unambiguous path returned by the discovery tool
        - **MATCH OPERATORS**: Only use operators compatible with the field type as confirmed by `{tools.get_valid_operators.__name__}`

        ### Steps
        1. If filters needed: Call {tools.discover_filter_paths.__name__}, {tools.get_valid_operators.__name__}, build FilterTree, call {tools.set_filter_tree.__name__}
        2. Call {tools.run_search.__name__}()
        3. Briefly confirm what was searched (1-2 sentences). DO NOT list results - UI shows them
    """
    ).strip()


def get_aggregation_execution_prompt(state: SearchState) -> str:
    """Get prompt for AggregationNode agent.

    Args:
        state: Current search state with query_operation and query info

    Returns:
        Complete prompt for executing aggregation with optional filtering and grouping
    """
    from orchestrator.search.core.types import QueryOperation

    env = state.environment
    conversation = env.format_for_llm(max_turns=3)
    query_operation = state.query_operation.value if state.query_operation else "unknown"

    return dedent(
        f"""
        ## Recent Conversation
        {conversation}

        ## Current Request
        "{state.user_input}"

        ---

        You are an expert assistant designed to find relevant information by building and running database queries.

        ### Your Task
        Execute an aggregation query (operation: {query_operation}) for the user's request.

        ### Filtering Rules (if query requires filters to restrict WHICH records)
        - Temporal constraints like "in 2025", "between X and Y" require filters on datetime fields
        - **NEVER GUESS PATHS IN THE DATABASE**: You *must* verify every filter path by calling `{tools.discover_filter_paths.__name__}` first
        - **START WITH SIMPLE NAMES**: For "active subscriptions", try "status" first, not "subscription.status" or variations
        - Common filter examples: "status", "name", "description", "start_date", "end_date", "customer_id"
        - If a path does not exist, you may attempt to map the question to existing paths that are valid
        - **USE FULL PATHS**: Always use the full, unambiguous path returned by the discovery tool
        - **MATCH OPERATORS**: Only use operators compatible with the field type as confirmed by `{tools.get_valid_operators.__name__}`
        - Filters restrict WHICH records; grouping controls HOW to aggregate

        ### Steps
        1. If filters needed: Call {tools.discover_filter_paths.__name__}, {tools.get_valid_operators.__name__}, build FilterTree, call {tools.set_filter_tree.__name__}
        2. Set grouping: Temporal ({tools.set_temporal_grouping.__name__}) or regular ({tools.set_grouping.__name__})
        3. For {QueryOperation.AGGREGATE.value} operation ONLY: Call {tools.set_aggregations.__name__}. For {QueryOperation.COUNT.value}: Do NOT call (counting is automatic)
        4. Call {tools.run_aggregation.__name__}(visualization_type=...)
        5. Briefly confirm what was computed (1-2 sentences). DO NOT list results - visualization shows them
    """
    ).strip()


def get_text_response_prompt(state: SearchState, is_forced_response: bool = False) -> str:
    """Get prompt for TextResponseNode agent.

    This node handles two cases:
    1. TEXT_RESPONSE intent: General questions, greetings, out-of-scope queries
    2. NO_MORE_ACTIONS intent: Completion acknowledgment (is_forced_response=True)

    Args:
        state: Current search state
        is_forced_response: If True, generate completion message because no actions were taken

    Returns:
        Complete prompt for generating text response
    """
    if is_forced_response:
        return dedent(
            f"""
            The user said: "{state.user_input}"

            The system determined no actions were needed for this request.

            Briefly acknowledge this and ask what they'd like to do next.

            Examples:
            - "Looks like that's already handled. What else can I help with?"
            - "Nothing more to do here. Anything else?"
            - "All set. What would you like next?"

            Keep it brief.
            """
        ).strip()

    # Normal TEXT_RESPONSE intent
    env = state.environment
    conversation = env.format_for_llm(max_turns=3)
    entity_types = ", ".join([et.value for et in EntityType])

    return dedent(
        f"""
        ## Recent Conversation
        {conversation}

        ## Current Request
        "{state.user_input}"

        ---

        You are a search assistant that helps users find and analyze data.

        Available capabilities:
        - Search for entities: {entity_types}
        - Filter searches by various criteria (status, dates, custom fields)
        - Count and aggregate data (totals, averages, grouping by fields or time periods)
        - Return structured data with visualization hints (table, bar chart, line chart, etc.)
        - Export search results
        - Fetch detailed information about specific entities

        Generate a helpful response to the user's question.
    """
    ).strip()


def get_intent_classification_prompt(state: SearchState) -> str:
    env = state.environment
    conversation = env.format_for_llm(max_turns=3)
    current_turn = env.format_current_turn()
    current_context = env.format_current_context()

    if state.visited_nodes:
        actions_list = "\n".join([f"- {node}: {action}" for node, action in state.visited_nodes.items()])
    else:
        actions_list = "None"

    return dedent(
        f"""
        # Intent Classification

        ## Recent Conversation
        {conversation}

        ## Current Turn
        {current_turn}

        ## Current Context
        {current_context}

        ## Actions in This Graph Run
        {actions_list}

        ## Current Request
        "{state.user_input}"

        ## Decision Rules
        1. Recent conversation is for reference
        2. Current context shows what's available for follow-up
        3. Execute actions for the CURRENT request
        4. Set end_actions=True if next action completes the request
        5. Use no_more_actions if no further actions needed

        Classify the user's intent for the NEXT single action.
        """
    ).strip()


def get_result_actions_prompt(state: SearchState) -> str:
    """Get prompt for ResultActionsNode agent.

    Args:
        state: Current search state with environment and user input

    Returns:
        Complete prompt for result actions
    """
    env = state.environment
    conversation = env.format_for_llm(max_turns=3)
    current_context = env.format_current_context()
    results_count = state.results_count or 0

    return dedent(
        f"""
        ## Recent Conversation
        {conversation}

        ## Current Request
        "{state.user_input}"

        ## Current Context
        {current_context}

        ---

        Act on existing search/aggregation results.

        Current state: {results_count} results available from previous query.

        Available actions:
        - If user wants to EXPORT/DOWNLOAD results: Call prepare_export() ONLY
        - If user wants DETAILED INFORMATION about entities: Call fetch_entity_details(limit=...)

        IMPORTANT: For export requests, ONLY call prepare_export(). Do NOT fetch entity details.

        Execute the requested action and provide a brief confirmation.
        """
    ).strip()

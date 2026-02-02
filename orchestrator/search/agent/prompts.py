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


def get_search_execution_prompt(state: SearchState) -> str:
    """Get prompt for SearchNode agent.

    Args:
        state: Current search state

    Returns:
        Complete prompt for executing search with optional filtering
    """
    return dedent(
        f"""
        You are an expert assistant designed to find relevant information by building and running database queries.

        ### Your Task
        Execute a database search to answer the user's request: "{state.user_input}"

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
        state: Current search state with action and query info

    Returns:
        Complete prompt for executing aggregation with optional filtering and grouping
    """
    from orchestrator.search.core.types import ActionType

    action = state.action.value if state.action else "unknown"

    return dedent(
        f"""
        You are an expert assistant designed to find relevant information by building and running database queries.

        ### Your Task
        Execute an aggregation query (action: {action}) for: "{state.user_input}"

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
        3. For {ActionType.AGGREGATE.value} action ONLY: Call {tools.set_aggregations.__name__}. For {ActionType.COUNT.value}: Do NOT call (counting is automatic)
        4. Call {tools.run_aggregation.__name__}(visualization_type=...)
        5. Briefly confirm what was computed (1-2 sentences). DO NOT list results - visualization shows them
    """
    ).strip()


def get_text_response_prompt(state: SearchState) -> str:
    """Get prompt for TextResponseNode agent.

    This node only handles TEXT_RESPONSE intent (general questions, greetings, out-of-scope).
    It never receives search/aggregation results since those flows end at execution nodes.

    Args:
        state: Current search state

    Returns:
        Complete prompt for generating text response
    """
    entity_types = ", ".join([et.value for et in EntityType])

    return dedent(
        f"""
        You are a search assistant that helps users find and analyze data.

        Available capabilities:
        - Search for entities: {entity_types}
        - Filter searches by various criteria (status, dates, custom fields)
        - Count and aggregate data (totals, averages, grouping by fields or time periods)
        - Return structured data with visualization hints (table, bar chart, line chart, etc.)
        - Export search results
        - Fetch detailed information about specific entities

        Generate a helpful response to the user's question.

        User request: {state.user_input}
    """
    ).strip()

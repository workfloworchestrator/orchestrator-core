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


def get_filter_building_prompt(state: SearchState) -> str:
    """Get prompt for FilterBuildingNode agent.

    Args:
        state: Current search state with user input and query info

    Returns:
        Complete prompt with instructions and user context
    """
    return dedent(
        f"""
        Build database query filters based on the user's request.

        Instructions:
        - Call {tools.discover_filter_paths.__name__} to find valid paths for filter criteria
        - Call {tools.get_valid_operators.__name__} to get compatible operators for those paths
        - Build FilterTree and call {tools.set_filter_tree.__name__}(filters=...)
        - Never guess paths - always verify with {tools.discover_filter_paths.__name__}
        - After calling tools, briefly state which filters you applied in one short sentence

        User request: {state.user_input}
    """
    ).strip()


def get_search_execution_prompt(state: SearchState) -> str:
    """Get prompt for SearchNode agent.

    Args:
        state: Current search state

    Returns:
        Complete prompt for executing search
    """
    return dedent(
        f"""
        Execute the database search by calling {tools.run_search.__name__}().
        After calling the tool, provide a brief final response:
        - Confirm what was searched
        - Mention the number of results found
        - Keep it concise (1-2 sentences)
        - Do NOT list individual results - the UI/visualization will show them

        User request: {state.user_input}
    """
    ).strip()


def get_aggregation_execution_prompt(state: SearchState) -> str:
    """Get prompt for AggregationNode agent.

    Args:
        state: Current search state with action and query info

    Returns:
        Complete prompt for executing aggregation
    """
    action = state.action.value if state.action else "unknown"

    return dedent(
        f"""
        Execute the aggregation query (action: {action}).

        Instructions:
        1. Set up grouping if needed:
           - For temporal: call {tools.set_temporal_grouping.__name__}()
           - For regular: call {tools.set_grouping.__name__}()
        2. For AGGREGATE action ONLY (not COUNT):
           - Call {tools.set_aggregations.__name__}() to specify what to compute
        3. Call {tools.run_aggregation.__name__}(visualization_type=...)
        4. Provide a brief final response:
           - Confirm what was computed/counted
           - Mention the number of result groups if relevant
           - Keep it concise (1-2 sentences)
           - Do NOT list the results - the visualization will show them

        User request: {state.user_input}
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

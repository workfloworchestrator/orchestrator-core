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

"""Search agent tools package."""

from orchestrator.search.agent.tools.aggregation import (
    aggregation_execution_toolset,
    aggregation_toolset,
    run_aggregation,
    set_aggregations,
    set_grouping,
    set_temporal_grouping,
)
from orchestrator.search.agent.tools.filters import (
    ensure_query_initialized,
    discover_filter_paths,
    filter_building_toolset,
    get_valid_operators,
    set_filter_tree,
)
from orchestrator.search.agent.tools.result_actions import (
    fetch_entity_details,
    prepare_export,
    result_actions_toolset,
)
from orchestrator.search.agent.tools.search import (
    run_search,
    search_execution_toolset,
)

__all__ = [
    "ensure_query_initialized",
    "aggregation_execution_toolset",
    "aggregation_toolset",
    "discover_filter_paths",
    "fetch_entity_details",
    "filter_building_toolset",
    "get_valid_operators",
    "prepare_export",
    "result_actions_toolset",
    "run_aggregation",
    "run_search",
    "search_execution_toolset",
    "set_aggregations",
    "set_filter_tree",
    "set_grouping",
    "set_temporal_grouping",
]

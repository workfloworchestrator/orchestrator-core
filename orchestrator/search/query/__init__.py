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

"""Query building and execution module."""

from orchestrator.search.aggregations import TemporalGrouping

from . import engine
from .builder import (
    ComponentInfo,
    LeafInfo,
    build_aggregation_query,
    build_candidate_query,
    build_paths_query,
    process_path_rows,
)
from .exceptions import (
    EmptyFilterPathError,
    IncompatibleAggregationTypeError,
    IncompatibleFilterTypeError,
    IncompatibleTemporalGroupingTypeError,
    InvalidEntityPrefixError,
    InvalidLtreePatternError,
    PathNotFoundError,
    QueryValidationError,
)
from .queries import AggregateQuery, CountQuery, ExportQuery, Query, SelectQuery
from .results import (
    AggregationResponse,
    AggregationResult,
    MatchingField,
    SearchResponse,
    SearchResult,
    VisualizationType,
    format_aggregation_response,
    format_search_response,
    generate_highlight_indices,
)
from .state import QueryState

__all__ = [
    # Builder functions
    "build_aggregation_query",
    "build_candidate_query",
    "build_paths_query",
    "process_path_rows",
    # Builder metadata
    "ComponentInfo",
    "LeafInfo",
    # Engine
    "engine",
    # Exceptions
    "EmptyFilterPathError",
    "IncompatibleAggregationTypeError",
    "IncompatibleFilterTypeError",
    "IncompatibleTemporalGroupingTypeError",
    "InvalidEntityPrefixError",
    "InvalidLtreePatternError",
    "PathNotFoundError",
    "QueryValidationError",
    # Query models
    "AggregateQuery",
    "CountQuery",
    "ExportQuery",
    "Query",
    "SelectQuery",
    "TemporalGrouping",
    # Results
    "AggregationResponse",
    "AggregationResult",
    "MatchingField",
    "SearchResponse",
    "SearchResult",
    "VisualizationType",
    "format_aggregation_response",
    "format_search_response",
    "generate_highlight_indices",
    # State
    "QueryState",
]

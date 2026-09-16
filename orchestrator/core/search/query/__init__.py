# Copyright 2019-2026 SURF, GÉANT.
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

from orchestrator.core.search.aggregations import TemporalGrouping
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.builder import (
    ComponentInfo,
    LeafInfo,
    build_aggregation_query,
    build_candidate_query,
    build_paths_query,
    build_response_column_rows_query,
    process_path_rows,
    process_response_flat_columns,
)
from orchestrator.core.search.query.exceptions import (
    EmptyFilterPathError,
    IncompatibleAggregationTypeError,
    IncompatibleFilterTypeError,
    IncompatibleTemporalGroupingTypeError,
    InvalidEntityPrefixError,
    InvalidLtreePatternError,
    PathNotFoundError,
    QueryValidationError,
)
from orchestrator.core.search.query.queries import AggregateQuery, CountQuery, ExportQuery, Query, SelectQuery
from orchestrator.core.search.query.results import (
    MatchingField,
    QueryResultsResponse,
    ResultRow,
    SearchResponse,
    SearchResult,
    VisualizationType,
    format_aggregation_response,
    format_search_response,
    generate_highlight_indices,
)
from orchestrator.core.search.query.state import QueryState

__all__ = [
    # Builder functions
    "build_aggregation_query",
    "build_candidate_query",
    "build_paths_query",
    "build_response_column_rows_query",
    "process_path_rows",
    "process_response_flat_columns",
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
    "QueryResultsResponse",
    "ResultRow",
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

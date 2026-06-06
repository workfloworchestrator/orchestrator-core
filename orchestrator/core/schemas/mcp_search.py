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

"""Request/response schemas for the search-engine MCP tools.

These mirror the (now removed) orchestrator-agent toolset: the agent used to
reach into the search engine directly; the same capability is now exposed as
self-contained MCP tools so any agent can drive search/aggregation over MCP.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.search.aggregations import Aggregation, TemporalGrouping
from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.fallback import SearchEffort
from orchestrator.core.search.filters import FilterTree
from orchestrator.core.search.query.mixins import OrderBy
from orchestrator.core.search.query.queries import BaseQuery

# --- Requests -------------------------------------------------------------


class SearchToolRequest(OrchestratorBaseModel):
    entity_type: EntityType = Field(description="Type of entity to search: SUBSCRIPTION, PRODUCT, WORKFLOW or PROCESS.")
    query_text: str | None = Field(
        default=None,
        description="Free-text query for semantic/fuzzy ranking (e.g. a name, description fragment, or id).",
    )
    filters: FilterTree | None = Field(
        default=None,
        description="Structured filter tree. Use discover_filter_paths and get_valid_operators to build valid paths/operators first.",
    )
    limit: int = Field(
        default=BaseQuery.DEFAULT_LIMIT,
        ge=BaseQuery.MIN_LIMIT,
        le=BaseQuery.MAX_LIMIT,
        description="Maximum number of results to return.",
    )
    retriever: RetrieverType | None = Field(
        default=None,
        description="Force a ranking strategy (FUZZY/SEMANTIC/HYBRID). Requires query_text. Omit to auto-route.",
    )
    effort: SearchEffort = Field(
        default=SearchEffort.MEDIUM,
        description="How hard to broaden when a filtered search returns nothing: 'high'=2 fallback passes, "
        "'medium'=1, 'low'=0 (report no matches instead of broadening). Each pass drops the filters and "
        "re-ranks by similarity to surface the closest matches.",
    )


class AggregateToolRequest(OrchestratorBaseModel):
    entity_type: EntityType = Field(description="Type of entity to aggregate over.")
    operation: Literal["count", "aggregate"] = Field(
        default="count",
        description="'count' to count rows (optionally grouped); 'aggregate' to compute SUM/AVG/MIN/MAX (requires aggregations).",
    )
    filters: FilterTree | None = Field(default=None, description="Structured filter tree to apply before aggregating.")
    group_by: list[str] | None = Field(default=None, description="Field paths to group by.")
    aggregations: list[Aggregation] | None = Field(
        default=None,
        description="Aggregations to compute (required when operation='aggregate').",
    )
    temporal_group_by: list[TemporalGrouping] | None = Field(
        default=None, description="Group datetime fields by time period (month, year, ...)."
    )
    cumulative: bool = Field(default=False, description="Running totals over a single temporal grouping.")
    order_by: list[OrderBy] | None = Field(
        default=None, description="Order grouped results by a grouping field or aggregation alias."
    )


class DiscoverFilterPathsRequest(OrchestratorBaseModel):
    field_names: list[str] = Field(description="Field names to look up filterable paths for (e.g. ['status', 'customer']).")
    entity_type: EntityType = Field(description="Entity type whose schema to search.")


class ResolveEntityRequest(OrchestratorBaseModel):
    id_or_prefix: str = Field(description="A full entity UUID or a partial id-prefix (at least 4 hex characters).")
    entity_type: EntityType = Field(description="Type of entity the id refers to.")


class ExportQueryRequest(OrchestratorBaseModel):
    query_id: UUID = Field(description="The query_id returned by a previous search call.")


# --- Responses ------------------------------------------------------------


class SearchToolResultItem(OrchestratorBaseModel):
    entity_id: str
    entity_type: EntityType
    title: str
    score: float


class SearchToolResponse(OrchestratorBaseModel):
    query_id: UUID = Field(description="Persisted query id; pass to export_query to download full results as CSV.")
    entity_type: EntityType
    returned: int = Field(description="Number of results returned in this response.")
    has_more: bool = Field(description="True if more matches exist beyond the returned limit.")
    search_type: str = Field(description="Which strategy produced these results (structured/semantic/fuzzy/hybrid).")
    fallback_used: bool = Field(
        default=False,
        description="True when the exact filtered search was empty and these are the closest matches "
        "(filters dropped, ranked by similarity) rather than exact matches — tell the user they are approximate.",
    )
    results: list[SearchToolResultItem]


class AggregateRow(OrchestratorBaseModel):
    group_values: dict[str, str] = {}
    aggregations: dict[str, float | int] = {}


class AggregateToolResponse(OrchestratorBaseModel):
    query_id: UUID
    total_results: int
    visualization: str = Field(description="Suggested visualization type (table, line, bar, ...).")
    results: list[AggregateRow]


class FieldPathDiscovery(OrchestratorBaseModel):
    status: Literal["OK", "NOT_FOUND"]
    guidance: str
    leaves: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []


class ResolvedCandidate(OrchestratorBaseModel):
    entity_id: str
    title: str


class ResolveEntityResponse(OrchestratorBaseModel):
    status: Literal["unique", "candidates", "not_found"]
    entity_type: EntityType
    entity_id: str | None = None
    title: str | None = None
    candidates: list[ResolvedCandidate] = []
    message: str


class ExportQueryResponse(OrchestratorBaseModel):
    query_id: UUID
    download_path: str = Field(description="Relative API path that streams the CSV export.")
    message: str

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

"""Query execution result models and formatting functions."""

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.engine.row import RowMapping

from orchestrator.search.core.types import EntityType, FilterOp, SearchMetadata
from orchestrator.search.filters import FilterTree

from .queries import AggregateQuery, CountQuery, ExportQuery, SelectQuery


class VisualizationType(BaseModel):
    """Visualization type for aggregation results.

    Choose based on the query context:
    - 'pie': For categorical distributions (e.g., subscriptions by status, products by type)
    - 'line': For time-series data (e.g., subscriptions created per month, trends over time)
    - 'table': For detailed data or multiple grouping dimensions (default)
    """

    type: Literal["pie", "line", "table"] = Field(
        default="table",
        description="Visualization render type: 'pie' for categorical distributions, 'line' for time-series, 'table' for detailed data",
    )


class MatchingField(BaseModel):
    """Contains the field that contributed most to the (fuzzy) search result."""

    text: str
    path: str
    highlight_indices: list[tuple[int, int]] | None = None


class SearchResult(BaseModel):
    """Represents a single search result item."""

    entity_id: str
    entity_type: EntityType
    entity_title: str
    score: float
    perfect_match: int = 0
    matching_field: MatchingField | None = None


class SearchResponse(BaseModel):
    """Response containing search results and metadata."""

    results: list[SearchResult]
    metadata: SearchMetadata
    query_embedding: list[float] | None = None
    has_more: bool = False


class AggregationResult(BaseModel):
    """Represents a single aggregation result row."""

    group_values: dict[str, str] = Field(default_factory=dict)  # group_by field -> value
    aggregations: dict[str, float | int] = Field(default_factory=dict)  # alias -> computed value

    model_config = ConfigDict(extra="forbid")


class AggregationResponse(BaseModel):
    """Response containing aggregation results."""

    results: list[AggregationResult]
    total_groups: int
    metadata: SearchMetadata
    visualization_type: VisualizationType = Field(default_factory=VisualizationType)

    model_config = ConfigDict(extra="forbid")


class ExportData(BaseModel):
    """Export metadata for download."""

    action: str = "export"
    query_id: str
    download_url: str
    message: str


def format_aggregation_response(
    result_rows: Sequence[RowMapping],
    group_column_names: list[str],
    query: CountQuery | AggregateQuery,
) -> AggregationResponse:
    """Format raw aggregation query results into AggregationResponse.

    Args:
        result_rows: Raw database result rows
        group_column_names: List of column names that are grouping columns
        query: Query plan for metadata

    Returns:
        AggregationResponse with formatted results and metadata
    """
    results = []
    for row in result_rows:
        group_values = {}
        aggregations = {}

        for key, value in row.items():
            if key in group_column_names:
                # It's a grouping column
                group_values[key] = str(value) if value is not None else ""
            else:
                # It's an aggregation result
                aggregations[key] = value if value is not None else 0

        results.append(AggregationResult(group_values=group_values, aggregations=aggregations))

    metadata = SearchMetadata(
        search_type="aggregation",
        description=f"Aggregation query with {len(query.group_by or [])} grouping dimension(s)",
    )

    return AggregationResponse(
        results=results,
        total_groups=len(results),
        metadata=metadata,
    )


def generate_highlight_indices(text: str, term: str) -> list[tuple[int, int]]:
    """Finds all occurrences of individual words from the term, including both word boundary and substring matches."""
    import re

    if not text or not term:
        return []

    all_matches = []
    words = [w.strip() for w in term.split() if w.strip()]

    for word in words:
        # First find word boundary matches
        word_boundary_pattern = rf"\b{re.escape(word)}\b"
        word_matches = list(re.finditer(word_boundary_pattern, text, re.IGNORECASE))
        all_matches.extend([(m.start(), m.end()) for m in word_matches])

        # Then find all substring matches
        substring_pattern = re.escape(word)
        substring_matches = list(re.finditer(substring_pattern, text, re.IGNORECASE))
        all_matches.extend([(m.start(), m.end()) for m in substring_matches])

    return sorted(set(all_matches))


def format_search_response(
    db_rows: Sequence[RowMapping], query: "SelectQuery | ExportQuery", metadata: SearchMetadata
) -> SearchResponse:
    """Format database query results into a `SearchResponse`.

    Converts raw SQLAlchemy `RowMapping` objects into `SearchResult` instances,
    including highlight metadata if present in the database results.

    Args:
        db_rows: The rows returned from the executed SQLAlchemy query.
        query: SelectQuery or ExportQuery with search criteria.
        metadata: Metadata about the search execution.

    Returns:
        SearchResponse: A list of `SearchResult` objects containing entity IDs, scores,
        and optional highlight information.
    """
    from orchestrator.search.retrieval.retrievers import Retriever

    if not db_rows:
        return SearchResponse(results=[], metadata=metadata)

    user_query = query.query_text

    results = []
    for row in db_rows:
        matching_field = None

        if (
            user_query
            and (text := row.get(Retriever.HIGHLIGHT_TEXT_LABEL)) is not None
            and (path := row.get(Retriever.HIGHLIGHT_PATH_LABEL)) is not None
        ):
            if not isinstance(text, str):
                text = str(text)
            if not isinstance(path, str):
                path = str(path)

            highlight_indices = generate_highlight_indices(text, user_query) or None
            matching_field = MatchingField(text=text, path=path, highlight_indices=highlight_indices)

        elif not user_query and query.filters and metadata.search_type == "structured":
            # Structured search (filter-only)
            matching_field = _extract_matching_field_from_filters(query.filters)

        entity_title = row.get("entity_title", "")
        if not isinstance(entity_title, str):
            entity_title = str(entity_title) if entity_title is not None else ""

        results.append(
            SearchResult(
                entity_id=str(row.entity_id),
                entity_type=query.entity_type,
                entity_title=entity_title,
                score=row.score,
                perfect_match=row.get("perfect_match", 0),
                matching_field=matching_field,
            )
        )
    return SearchResponse(results=results, metadata=metadata)


def _extract_matching_field_from_filters(filters: "FilterTree") -> MatchingField | None:
    """Extract the first path filter to use as matching field for structured searches."""
    from orchestrator.search.filters import LtreeFilter

    leaves = filters.get_all_leaves()
    if len(leaves) != 1:
        return None

    pf = leaves[0]

    if isinstance(pf.condition, LtreeFilter):
        op = pf.condition.op
        # Prefer the original component/pattern (validator may set path="*" and move the value)
        display = str(getattr(pf.condition, "value", "") or pf.path)

        # There can be no match for abscence.
        if op == FilterOp.NOT_HAS_COMPONENT:
            return None

        return MatchingField(text=display, path=display, highlight_indices=[(0, len(display))])

    # Everything thats not Ltree
    val = getattr(pf.condition, "value", "")
    text = "" if val is None else str(val)
    return MatchingField(text=text, path=pf.path, highlight_indices=[(0, len(text))])

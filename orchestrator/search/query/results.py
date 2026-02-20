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


class ResultRow(BaseModel):
    """A single result row with labeled string columns and numeric columns."""

    group_values: dict[str, str] = Field(default_factory=dict)
    aggregations: dict[str, float | int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class QueryResultsResponse(BaseModel):
    """Tabular query results used for both search and aggregation rendering."""

    results: list[ResultRow]
    total_results: int
    metadata: SearchMetadata
    visualization_type: VisualizationType = Field(default_factory=VisualizationType)

    model_config = ConfigDict(extra="forbid")


class QueryArtifact(BaseModel):
    """Lightweight reference returned by query tools.

    Client fetches full results via GET /queries/{query_id}/results.
    """

    query_id: str
    total_results: int
    visualization_type: VisualizationType = Field(default_factory=VisualizationType)
    description: str


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
) -> QueryResultsResponse:
    """Format raw aggregation query results into QueryResultsResponse.

    Args:
        result_rows: Raw database result rows
        group_column_names: List of column names that are grouping columns
        query: Query plan for metadata

    Returns:
        QueryResultsResponse with formatted results and metadata
    """
    results = []
    for row in result_rows:
        group_values = {}
        aggregations = {}

        for key, value in row.items():
            if key in group_column_names:
                group_values[key] = str(value) if value is not None else ""
            else:
                aggregations[key] = value if value is not None else 0

        results.append(ResultRow(group_values=group_values, aggregations=aggregations))

    metadata = SearchMetadata(
        search_type="aggregation",
        description=f"Aggregation query with {len(query.group_by or [])} grouping dimension(s)",
    )

    return QueryResultsResponse(
        results=results,
        total_results=len(results),
        metadata=metadata,
    )


def truncate_text_with_highlights(
    text: str, highlight_indices: list[tuple[int, int]] | None = None, max_length: int = 500, context_chars: int = 100
) -> tuple[str, list[tuple[int, int]] | None]:
    """Truncate text to max_length while preserving context around the first highlight.

    Args:
        text: The text to truncate
        highlight_indices: List of (start, end) tuples indicating highlight positions, or None
        max_length: Maximum length of the returned text
        context_chars: Number of characters to show before and after the first highlight

    Returns:
        Tuple of (truncated_text, adjusted_highlight_indices)
    """
    # If text is short enough, return as-is
    if len(text) <= max_length:
        return text, highlight_indices

    # If no highlights, truncate from beginning
    if not highlight_indices:
        truncated_text = text[:max_length]
        suffix = "..." if len(text) > max_length else ""
        return truncated_text + suffix, None

    # Use first highlight to determine what to show
    first_highlight_start = highlight_indices[0][0]

    # Calculate start position: try to center around first highlight
    start = max(0, first_highlight_start - context_chars)
    end = min(len(text), start + max_length)

    # Adjust start if we hit the end boundary
    if end == len(text) and (end - start) < max_length:
        start = max(0, end - max_length)

    truncated_text = text[start:end]

    # Add ellipsis to indicate truncation
    truncated_from_start = start > 0
    truncated_from_end = end < len(text)

    if truncated_from_start:
        truncated_text = "..." + truncated_text
    if truncated_from_end:
        truncated_text = truncated_text + "..."

    # Adjust highlight indices to be relative to truncated text
    offset = start - (3 if truncated_from_start else 0)  # Account for leading "..."
    adjusted_indices = []
    for hl_start, hl_end in highlight_indices:
        # Only include highlights that are within the truncated range
        if hl_start >= start and hl_end <= end:
            adjusted_indices.append((hl_start - offset, hl_end - offset))

    return truncated_text, adjusted_indices if adjusted_indices else None


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

            highlight_indices = generate_highlight_indices(text, user_query)
            truncated_text, adjusted_indices = truncate_text_with_highlights(text, highlight_indices)
            matching_field = MatchingField(text=truncated_text, path=path, highlight_indices=adjusted_indices)

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

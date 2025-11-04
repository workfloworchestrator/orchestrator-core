import uuid

from pydantic import BaseModel, Field

from orchestrator.search.aggregations import Aggregation, TemporalGrouping

__all__ = [
    "SearchMixin",
    "GroupingMixin",
    "AggregationMixin",
]


class SearchMixin(BaseModel):
    """Mixin providing text search capability.

    Provides query text processing and derived properties for vector and fuzzy search.
    """

    query_text: str | None = Field(default=None, description="Text query for semantic/fuzzy search")

    @property
    def vector_query(self) -> str | None:
        """Extract vector query from query text.

        Returns None if query_text is empty or is a UUID (UUIDs are not vectorized).
        This matches the original logic from BaseQuery.
        """
        if not self.query_text:
            return None
        try:
            uuid.UUID(self.query_text)
            return None  # It's a UUID, disable vector search
        except ValueError:
            return self.query_text

    @property
    def fuzzy_term(self) -> str | None:
        """Extract fuzzy term from query text.

        Only single-word queries are used for fuzzy search to avoid
        the trigram operator filtering out too many results.
        This matches the original logic from BaseQuery.
        """
        if not self.query_text:
            return None
        words = self.query_text.split()
        return self.query_text if len(words) == 1 else None


class GroupingMixin(BaseModel):
    """Mixin providing grouping capability.

    Used by COUNT and AGGREGATE queries for grouping results.
    """

    group_by: list[str] | None = Field(default=None, description="Field paths to group by")
    temporal_group_by: list[TemporalGrouping] | None = Field(
        default=None,
        description="Temporal grouping specifications (group by month, year, etc.)",
    )

    def get_pivot_fields(self) -> list[str]:
        """Get all fields needed for EAV pivot from grouping.

        Returns deduplicated list maintaining insertion order.
        This matches the original logic from BaseQuery.get_pivot_fields().
        """
        fields = list(self.group_by or [])

        # Collect from temporal groupings
        if self.temporal_group_by:
            for temp_group in self.temporal_group_by:
                fields.extend(temp_group.get_pivot_fields())

        return list(dict.fromkeys(fields))


class AggregationMixin(BaseModel):
    """Mixin providing aggregation computation capability.

    Used by AGGREGATE queries to define what statistics to compute.
    """

    aggregations: list[Aggregation] = Field(description="Aggregations to compute (SUM, AVG, MIN, MAX, COUNT)")

    def get_aggregation_pivot_fields(self) -> list[str]:
        """Get fields needed for EAV pivot from aggregations.

        Returns deduplicated list maintaining insertion order.
        """
        fields = []
        for agg in self.aggregations:
            fields.extend(agg.get_pivot_fields())
        return list(dict.fromkeys(fields))

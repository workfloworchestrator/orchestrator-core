import uuid
from enum import Enum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from orchestrator.search.aggregations import Aggregation, TemporalGrouping
from orchestrator.search.core.types import RetrieverType

__all__ = [
    "SearchMixin",
    "GroupingMixin",
    "AggregationMixin",
    "OrderBy",
    "OrderDirection",
]


class OrderDirection(str, Enum):
    """Sorting direction for aggregation results."""

    ASC = "asc"
    DESC = "desc"


class OrderBy(BaseModel):
    """Ordering descriptor for aggregation responses."""

    field: str = Field(description="Grouping or aggregation field/alias to order by.")
    direction: OrderDirection = Field(
        default=OrderDirection.ASC,
        description="Sorting direction (asc or desc).",
    )


class SearchMixin(BaseModel):
    """Mixin providing text search capability.

    Provides query text processing and derived properties for vector and fuzzy search.
    """

    query_text: str | None = Field(default=None, description="Text query for semantic/fuzzy search")
    retriever: RetrieverType | None = Field(
        default=None,
        description="Override retriever type (fuzzy/semantic/hybrid). If None, uses default routing logic.",
    )

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
    cumulative: bool = Field(
        default=False,
        description="Enable cumulative aggregations when temporal grouping is present.",
    )
    order_by: list[OrderBy] | None = Field(
        default=None,
        description="Ordering instructions for grouped aggregation results.",
    )

    @model_validator(mode="after")
    def validate_grouping_constraints(self) -> Self:
        """Validate cross-field constraints for grouping features."""
        if self.order_by and not self.group_by and not self.temporal_group_by:
            raise ValueError(
                "order_by requires at least one grouping field (group_by or temporal_group_by). "
                "Ordering only applies to grouped aggregation results."
            )

        if self.cumulative:
            if not self.temporal_group_by:
                raise ValueError(
                    "cumulative requires at least one temporal grouping (temporal_group_by). "
                    "Cumulative aggregations compute running totals over time."
                )
            if len(self.temporal_group_by) > 1:
                raise ValueError(
                    "cumulative currently supports only a single temporal grouping. "
                    "Multiple temporal dimensions with running totals are not yet supported."
                )

        return self

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

    aggregations: list[Aggregation] = Field(
        default_factory=list,
        description="Aggregations to compute (SUM, AVG, MIN, MAX, COUNT). Must be set before execution.",
    )

    def get_aggregation_pivot_fields(self) -> list[str]:
        """Get fields needed for EAV pivot from aggregations.

        Returns deduplicated list maintaining insertion order.
        """
        fields = []
        for agg in self.aggregations:
            fields.extend(agg.get_pivot_fields())
        return list(dict.fromkeys(fields))

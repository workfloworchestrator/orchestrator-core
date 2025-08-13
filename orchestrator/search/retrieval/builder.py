from typing import Optional

from sqlalchemy import Select, and_, select
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.filters import FilterSet, LtreeFilter
from orchestrator.search.schemas.parameters import BaseSearchParameters


class QueryBuilder:
    """Constructs SQLAlchemy queries to retrieve candidate entities.

    This class encapsulates logic for building the base query and applying
    structured search filters on indexed entity data.
    """

    def build(self, params: BaseSearchParameters) -> Select:
        """Build the base query for retrieving candidate entities.

        Constructs a `SELECT` statement that retrieves distinct `entity_id` values
        from the index table for the given entity type, applying any structured
        filters from the provided search parameters.

        Parameters
        ----------
        params : BaseSearchParameters
            The search parameters containing the entity type and optional filters.

        Returns:
        -------
        Select
            The SQLAlchemy `Select` object representing the query.
        """
        stmt = select(AiSearchIndex.entity_id).where(AiSearchIndex.entity_type == params.entity_type.value).distinct()

        # Apply all structured filters from the search parameters
        return self._apply_filters(stmt, params.filters)

    def _apply_filters(self, stmt: Select, filters: Optional[FilterSet] = None) -> Select:
        """Apply structured path-based filters to the query.

        For each filter in the provided list, joins the index table and applies
        the filter's SQLAlchemy expression. Handles both `LtreeFilter` path
        filters and value-based filters.

        Parameters
        ----------
        stmt : Select
            The base SQLAlchemy `Select` statement to modify.
        filters : Optional[FilterSet]
            A list of `PathFilter` objects representing the filter conditions.

        Returns:
        -------
        Select
            The modified SQLAlchemy `Select` statement with all filters applied.
        """
        if not filters:
            return stmt

        for i, path_filter in enumerate(filters):
            filter_alias = AiSearchIndex.__table__.alias(f"filter_{i}")  # type: ignore

            stmt = stmt.join(filter_alias, filter_alias.c.entity_id == AiSearchIndex.entity_id)

            if isinstance(path_filter.condition, LtreeFilter):
                # LTree only applies to path
                stmt = stmt.where(path_filter.to_expression(filter_alias.c.path))
            else:
                # We have to change this once we introduce nested groupings in our filters.
                stmt = stmt.where(
                    and_(
                        filter_alias.c.path == Ltree(path_filter.path),
                        path_filter.to_expression(filter_alias.c.value),
                    )
                )
        return stmt

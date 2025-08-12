from typing import Optional

from sqlalchemy import Select, and_, select
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.search.filters import FilterSet, LtreeFilter
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.schemas.parameters import BaseSearchParameters


class QueryBuilder:
    """
    Constructs the initial query to find a candidate set of entities.
    """

    def build(self, params: BaseSearchParameters) -> Select:
        """
        Builds the base query to find all candidate entity_ids based on
        the entity type and any structured filters.
        """
        stmt = select(AiSearchIndex.entity_id).where(AiSearchIndex.entity_type == params.entity_type.value).distinct()

        # Apply all structured filters from the search parameters
        stmt = self._apply_filters(stmt, params.filters)

        return stmt

    def _apply_filters(self, stmt: Select, filters: Optional[FilterSet] = None) -> Select:
        """
        Applies a list of PathFilter objects to the query by joining the index
        table for each filter condition.
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

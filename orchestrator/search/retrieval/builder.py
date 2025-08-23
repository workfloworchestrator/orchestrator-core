from sqlalchemy import Select, String, cast, func, select

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import EntityType, FilterOp
from orchestrator.search.filters import LtreeFilter
from orchestrator.search.schemas.parameters import BaseSearchParameters


def create_path_autocomplete_lquery(prefix: str) -> str:
    """Create the lquery pattern for a multi-level path autocomplete search."""
    return f"{prefix}*.*"


def build_candidate_query(params: BaseSearchParameters) -> Select:
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

    if params.filters is not None:
        entity_id_col = AiSearchIndex.entity_id
        stmt = stmt.where(
            params.filters.to_expression(
                entity_id_col,
                entity_type_value=params.entity_type.value,
            )
        )

    return stmt


def build_paths_query(entity_type: EntityType, prefix: str | None = None, q: str | None = None) -> Select:
    """Build the query for retrieving paths."""
    stmt = select(AiSearchIndex.path, AiSearchIndex.value_type).where(AiSearchIndex.entity_type == entity_type.value)

    if prefix:
        lquery_pattern = create_path_autocomplete_lquery(prefix)
        ltree_filter = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value=lquery_pattern)
        stmt = stmt.where(ltree_filter.to_expression(AiSearchIndex.path, path=""))

    if q:
        score = func.similarity(cast(AiSearchIndex.path, String), q).label("score")
        stmt = (
            stmt.add_columns(score)
            .group_by(AiSearchIndex.path, AiSearchIndex.value_type, score)
            .order_by(score.desc(), AiSearchIndex.path)
        )
    else:
        stmt = stmt.group_by(AiSearchIndex.path, AiSearchIndex.value_type).order_by(AiSearchIndex.path)

    return stmt

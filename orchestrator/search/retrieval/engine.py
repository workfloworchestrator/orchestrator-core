import structlog
from sqlalchemy.orm import Session
from sqlalchemy.engine.row import RowMapping
from typing import Sequence

from .builder import QueryBuilder
from .ranker import Ranker
from .utils import generate_highlight_indices
from orchestrator.search.schemas.parameters import BaseSearchParameters
from orchestrator.search.schemas.results import SearchResponse, SearchResult, Highlight

logger = structlog.get_logger(__name__)


def _format_response(db_rows: Sequence[RowMapping], search_params: BaseSearchParameters) -> SearchResponse:
    """Formats raw database rows into the final SearchResponse, including highlights."""
    response: SearchResponse = []
    for row in db_rows:
        highlight = None
        if search_params.fuzzy_term and row.get("highlight_text"):
            text = row.highlight_text
            indices = generate_highlight_indices(text, search_params.fuzzy_term)
            if indices:
                highlight = Highlight(text=text, indices=indices)

        response.append(
            SearchResult(
                entity_id=str(row.entity_id),
                score=row.score,
                highlight=highlight,
            )
        )
    return response


def execute_search(search_params: BaseSearchParameters, db_session: Session, limit: int = 5) -> SearchResponse:
    """
    Executes a search by building a candidate query, applying a ranking
    strategy, and executing the final query.
    """
    if not search_params.vector_query and not search_params.filters and not search_params.fuzzy_term:
        logger.warning("No search criteria provided (vector_query, fuzzy_term, or filters).")
        return []

    builder = QueryBuilder()
    candidate_query = builder.build(search_params)

    ranker = Ranker.from_params(search_params)
    logger.debug("Using ranker", ranker_type=ranker.__class__.__name__)

    final_stmt = ranker.apply(candidate_query)
    final_stmt = final_stmt.limit(limit)
    logger.debug(final_stmt)
    result = db_session.execute(final_stmt).mappings().all()

    return _format_response(result, search_params)

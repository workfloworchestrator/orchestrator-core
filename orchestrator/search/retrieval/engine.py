from collections.abc import Sequence

import structlog
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.orm import Session

from orchestrator.search.schemas.parameters import BaseSearchParameters
from orchestrator.search.schemas.results import Highlight, SearchResponse, SearchResult

from .builder import build_candidate_query
from .ranker import Ranker
from .utils import generate_highlight_indices

logger = structlog.get_logger(__name__)


def _format_response(db_rows: Sequence[RowMapping], search_params: BaseSearchParameters) -> SearchResponse:
    """Format database query results into a `SearchResponse`.

    Converts raw SQLAlchemy `RowMapping` objects into `SearchResult` instances,
    optionally generating highlight metadata if a fuzzy term is present.

    Parameters
    ----------
    db_rows : Sequence[RowMapping]
        The rows returned from the executed SQLAlchemy query.
    search_params : BaseSearchParameters
        The parameters used for the search, including any fuzzy term for highlighting.

    Returns:
    -------
    SearchResponse
        A list of `SearchResult` objects containing entity IDs, scores, and
        optional highlight information.
    """
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


async def execute_search(search_params: BaseSearchParameters, db_session: Session, limit: int = 5) -> SearchResponse:
    """Execute a hybrid search and return ranked results.

    Builds a candidate entity query based on the given search parameters,
    applies the appropriate ranking strategy, and executes the final ranked
    query to retrieve results.

    Parameters
    ----------
    search_params : BaseSearchParameters
        The search parameters specifying vector, fuzzy, or filter criteria.
    db_session : Session
        The active SQLAlchemy session for executing the query.
    limit : int, optional
        The maximum number of search results to return, by default 5.

    Returns:
    -------
    SearchResponse
        A list of `SearchResult` objects containing entity IDs, scores, and
        optional highlight metadata.

    Notes:
    -----
    If no vector query, filters, or fuzzy term are provided, a warning is logged
    and an empty result set is returned.
    """
    if not search_params.vector_query and not search_params.filters and not search_params.fuzzy_term:
        logger.warning("No search criteria provided (vector_query, fuzzy_term, or filters).")
        return []

    candidate_query = build_candidate_query(search_params)

    ranker = await Ranker.from_params(search_params)
    logger.debug("Using ranker", ranker_type=ranker.__class__.__name__)

    final_stmt = ranker.apply(candidate_query)
    final_stmt = final_stmt.limit(limit)
    logger.debug(final_stmt)
    result = db_session.execute(final_stmt).mappings().all()

    return _format_response(result, search_params)

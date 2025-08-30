from collections.abc import Sequence

import structlog
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.orm import Session

from orchestrator.search.core.types import SearchMetadata
from orchestrator.search.schemas.parameters import BaseSearchParameters
from orchestrator.search.schemas.results import MatchingField, SearchResponse, SearchResult

from .builder import build_candidate_query
from .pagination import PaginationParams
from .ranker import Ranker
from .utils import generate_highlight_indices

logger = structlog.get_logger(__name__)


def _format_response(
    db_rows: Sequence[RowMapping], search_params: BaseSearchParameters, metadata: SearchMetadata
) -> SearchResponse:
    """Format database query results into a `SearchResponse`.

    Converts raw SQLAlchemy `RowMapping` objects into `SearchResult` instances,
    including highlight metadata if present in the database results.

    Parameters
    ----------
    db_rows : Sequence[RowMapping]
        The rows returned from the executed SQLAlchemy query.

    Returns:
    -------
    SearchResponse
        A list of `SearchResult` objects containing entity IDs, scores, and
        optional highlight information.
    """

    if not db_rows:
        return SearchResponse(results=[], metadata=metadata)

    user_query = search_params.query

    results = []
    for row in db_rows:
        matching_field = None

        if user_query and row.get("highlight_text") and row.get("highlight_path"):
            text = row.highlight_text
            path = row.highlight_path

            if not isinstance(text, str):
                text = str(text)
            if not isinstance(path, str):
                path = str(path)

            highlight_indices = generate_highlight_indices(text, user_query) or None
            matching_field = MatchingField(text=text, path=path, highlight_indices=highlight_indices)

        results.append(
            SearchResult(
                entity_id=str(row.entity_id),
                score=row.score,
                perfect_match=row.get("perfect_match", 1),
                matching_field=matching_field,
            )
        )
    return SearchResponse(results=results, metadata=metadata)


async def execute_search(
    search_params: BaseSearchParameters,
    db_session: Session,
    pagination_params: PaginationParams | None = None,
) -> SearchResponse:
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
        return SearchResponse(results=[], metadata=SearchMetadata.empty())

    candidate_query = build_candidate_query(search_params)

    pagination_params = pagination_params or PaginationParams()
    ranker = await Ranker.from_params(search_params, pagination_params)
    logger.debug("Using ranker", ranker_type=ranker.__class__.__name__)

    final_stmt = ranker.apply(candidate_query)
    final_stmt = final_stmt.limit(search_params.limit)
    logger.debug(final_stmt)
    result = db_session.execute(final_stmt).mappings().all()

    return _format_response(result, search_params, ranker.metadata)

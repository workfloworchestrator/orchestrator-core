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

from collections.abc import Sequence

import structlog
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.orm import Session

from orchestrator.search.core.types import FilterOp, SearchMetadata
from orchestrator.search.filters import FilterTree, LtreeFilter
from orchestrator.search.schemas.parameters import BaseSearchParameters
from orchestrator.search.schemas.results import MatchingField, SearchResponse, SearchResult

from .builder import build_candidate_query
from .pagination import PaginationParams
from .retrievers import Retriever
from .utils import generate_highlight_indices

logger = structlog.get_logger(__name__)


def _format_response(
    db_rows: Sequence[RowMapping], search_params: BaseSearchParameters, metadata: SearchMetadata
) -> SearchResponse:
    """Format database query results into a `SearchResponse`.

    Converts raw SQLAlchemy `RowMapping` objects into `SearchResult` instances,
    including highlight metadata if present in the database results.

    Args:
        db_rows (Sequence[RowMapping]): The rows returned from the executed SQLAlchemy query.
        search_params (BaseSearchParameters): The search parameters, including query text and filters.
        metadata (SearchMetadata): Metadata about the search execution.

    Returns:
        SearchResponse: A list of `SearchResult` objects containing entity IDs, scores,
        and optional highlight information.
    """

    if not db_rows:
        return SearchResponse(results=[], metadata=metadata)

    user_query = search_params.query

    results = []
    for row in db_rows:
        matching_field = None

        if (
            user_query
            and (text := row.get(Retriever.HIGHLIGHT_TEXT_LABEL))
            and (path := row.get(Retriever.HIGHLIGHT_PATH_LABEL))
        ):
            if not isinstance(text, str):
                text = str(text)
            if not isinstance(path, str):
                path = str(path)

            highlight_indices = generate_highlight_indices(text, user_query) or None
            matching_field = MatchingField(text=text, path=path, highlight_indices=highlight_indices)

        elif not user_query and search_params.filters and metadata.search_type == "structured":
            # Structured search (filter-only)
            matching_field = _extract_matching_field_from_filters(search_params.filters)

        results.append(
            SearchResult(
                entity_id=str(row.entity_id),
                score=row.score,
                perfect_match=row.get("perfect_match", 0),
                matching_field=matching_field,
            )
        )
    return SearchResponse(results=results, metadata=metadata)


def _extract_matching_field_from_filters(filters: FilterTree) -> MatchingField | None:
    """Extract the first path filter to use as matching field for structured searches.

    TODO: Should we allow a list of matched fields in the MatchingField model?
    We need a different approach, probably a cross join in StructuredRetriever.
    """
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


async def execute_search(
    search_params: BaseSearchParameters,
    db_session: Session,
    pagination_params: PaginationParams | None = None,
) -> SearchResponse:
    """Execute a hybrid search and return ranked results.

    Builds a candidate entity query based on the given search parameters,
    applies the appropriate ranking strategy, and executes the final ranked
    query to retrieve results.

    Args:
        search_params (BaseSearchParameters): The search parameters specifying vector, fuzzy, or filter criteria.
        db_session (Session): The active SQLAlchemy session for executing the query.
        pagination_params (PaginationParams): Parameters controlling pagination of the search results.
        limit (int, optional): The maximum number of search results to return, by default 5.

    Returns:
        SearchResponse: A list of `SearchResult` objects containing entity IDs, scores,
        and optional highlight metadata.

    Notes:
        If no vector query, filters, or fuzzy term are provided, a warning is logged
        and an empty result set is returned.
    """

    if not search_params.vector_query and not search_params.filters and not search_params.fuzzy_term:
        logger.warning("No search criteria provided (vector_query, fuzzy_term, or filters).")
        return SearchResponse(results=[], metadata=SearchMetadata.empty())

    candidate_query = build_candidate_query(search_params)

    pagination_params = pagination_params or PaginationParams()
    retriever = await Retriever.from_params(search_params, pagination_params)
    logger.debug("Using retriever", retriever_type=retriever.__class__.__name__)

    final_stmt = retriever.apply(candidate_query)
    final_stmt = final_stmt.limit(search_params.limit)
    logger.debug(final_stmt)
    result = db_session.execute(final_stmt).mappings().all()

    return _format_response(result, search_params, retriever.metadata)

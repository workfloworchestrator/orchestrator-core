# Copyright 2019-2026 SURF, GÉANT.
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

"""Empty-result broadening waterfall for the agent-facing ``search`` tool.

Behaviour-preserving port of the orchestrator-agent ``run_search`` fallback: when a
structured search returns nothing, progressively drop the filters and re-rank by
similarity so the user still gets the closest matches instead of an empty result.
The number of broadening passes is governed by ``effort`` (HIGH=2, MEDIUM=1, LOW=0).
"""

from __future__ import annotations

from enum import Enum

import structlog

from orchestrator.core.db.database import WrappedSession
from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.filters import FilterTree
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.query.results import SearchResponse
from orchestrator.core.settings import llm_settings

logger = structlog.get_logger(__name__)


class SearchEffort(str, Enum):
    """How persistently search broadens before giving up (controls fallback passes)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Ordered broadening passes tried (in order) when a filtered search returns nothing.
# SEMANTIC first because it applies no similarity threshold and is effectively guaranteed
# non-empty; None (auto-routing) is the wider net that degrades to fuzzy in the engine.
_FALLBACK_RETRIEVER_ORDER: tuple[RetrieverType | None, ...] = (RetrieverType.SEMANTIC, None)

# How many of the above passes each effort level is allowed to run.
_EFFORT_FALLBACK_PASSES: dict[SearchEffort, int] = {
    SearchEffort.LOW: 0,
    SearchEffort.MEDIUM: 1,
    SearchEffort.HIGH: 2,
}


def _effective_retriever(requested: RetrieverType | None) -> RetrieverType | None:
    """Resolve the retriever to actually use, accounting for embedding availability.

    SEMANTIC and HYBRID need embeddings; when EMBEDDING_API_ENABLED is False they would
    raise ValueError in the engine. Degrade those to FUZZY (which still keyword-matches
    the identifier). FUZZY and None (auto-routing) pass through unchanged.
    """
    if requested in (RetrieverType.SEMANTIC, RetrieverType.HYBRID) and not llm_settings.EMBEDDING_API_ENABLED:
        return RetrieverType.FUZZY
    return requested


async def _attempt_semantic_query(
    retriever: RetrieverType | None,
    *,
    entity_type: EntityType,
    query_text: str,
    limit: int,
    db_session: WrappedSession,
) -> tuple[SearchResponse, SelectQuery] | None:
    """Run one filterless ranking pass; return it (with its query) only if it produced rows.

    A ValueError means the embedding was unavailable for an explicit retriever override —
    treat it as "no help" so the caller can try the next strategy.
    """
    query = SelectQuery(
        entity_type=entity_type,
        query_text=query_text,
        filters=None,
        retriever=retriever,
        limit=limit,
    )
    try:
        response = await engine.execute_search(query, db_session)
    except ValueError as exc:
        logger.debug("Semantic fallback attempt unavailable", retriever=retriever, error=str(exc))
        return None
    return (response, query) if response.results else None


async def _run_semantic_fallback(
    *,
    entity_type: EntityType,
    query_text: str,
    limit: int,
    db_session: WrappedSession,
    passes: int,
) -> tuple[SearchResponse, SelectQuery] | None:
    """Run up to ``passes`` filterless broadening searches, returning the first with rows.

    Tries the retrievers in ``_FALLBACK_RETRIEVER_ORDER`` (SEMANTIC, then auto-routed) up to
    ``passes`` times. SemanticRetriever applies no similarity threshold, so with filters
    dropped it returns the closest N embedded entities and is effectively guaranteed
    non-empty. ``passes == 0`` disables broadening entirely.
    """
    for retriever in _FALLBACK_RETRIEVER_ORDER[:passes]:
        result = await _attempt_semantic_query(
            retriever,
            entity_type=entity_type,
            query_text=query_text,
            limit=limit,
            db_session=db_session,
        )
        if result is not None:
            return result
    return None


async def execute_search_with_fallback(
    *,
    entity_type: EntityType,
    query_text: str | None,
    filters: FilterTree | None,
    limit: int,
    retriever: RetrieverType | None,
    effort: SearchEffort,
    db_session: WrappedSession,
) -> tuple[SearchResponse, SelectQuery, bool]:
    """Run the structured pass, then a semantic fallback when it returns zero rows.

    The number of broadening fallback passes is governed by ``effort``: HIGH=2, MEDIUM=1,
    LOW=0. Returns ``(response, executed_query, fallback_used)`` where ``executed_query`` is
    the query that produced the returned rows (the broadened one when ``fallback_used``) so
    the caller can persist it for export/pagination.
    """
    effective = _effective_retriever(retriever) if query_text else None
    query = SelectQuery(
        entity_type=entity_type,
        query_text=query_text,
        filters=filters,
        limit=limit,
        retriever=effective,
    )
    response = await engine.execute_search(query, db_session)

    # Results found, or nothing to broaden on (no free-text query) → return the exact pass.
    if response.results or not query_text:
        return response, query, False

    fallback = await _run_semantic_fallback(
        entity_type=entity_type,
        query_text=query_text,
        limit=limit,
        db_session=db_session,
        passes=_EFFORT_FALLBACK_PASSES[effort],
    )
    if fallback is None:
        return response, query, False

    fb_response, fb_query = fallback
    return fb_response, fb_query, True

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

When a structured search returns nothing, broaden progressively so the user still gets
the closest matches instead of an empty result, without discarding the high-signal part
of the query: first relax only the loose text filters while keeping the exact id/status/
customer filters, then drop all filters and rank by HYBRID (keyword-matches identifiers)
before SEMANTIC. Fallback passes degrade to FUZZY when embeddings are unavailable. The
number of broadening passes is governed by ``effort`` (HIGH=3, MEDIUM=1, LOW=0).
"""

from __future__ import annotations

from enum import Enum

import structlog

from orchestrator.core.db.database import WrappedSession
from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.filters import FilterTree, PathFilter, StringFilter
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


# How many broadening rungs each effort level may try when a filtered search is empty.
# HIGH=3 so it can exhaust the full ladder (relaxed filters, then HYBRID, then SEMANTIC).
_EFFORT_FALLBACK_PASSES: dict[SearchEffort, int] = {
    SearchEffort.LOW: 0,
    SearchEffort.MEDIUM: 1,
    SearchEffort.HIGH: 3,
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


def _is_relaxable(leaf: PathFilter) -> bool:
    """A loose text leaf (``like``/substring) — the first thing to drop when a filtered search is empty.

    Exact (``eq``/``neq``), range, and component filters carry high signal (ids, status,
    customer, dates) and are kept; only string filters are relaxed.
    """
    return isinstance(leaf.condition, StringFilter)


def _high_signal_filters(filters: FilterTree | None) -> FilterTree | None:
    """Drop loose text leaves, keeping the high-signal exact/range leaves as a flat AND.

    Returns None when relaxing is not a useful step: no filters, nothing relaxable (the
    reduced tree would equal the original), or nothing high-signal to keep (the reduced tree
    would be filterless, i.e. the next rung). Any nested OR structure is intentionally
    flattened to an AND of the kept leaves, which only ever broadens the candidate set.
    """
    if filters is None:
        return None
    leaves = filters.get_all_leaves()
    relaxable = [leaf for leaf in leaves if _is_relaxable(leaf)]
    high_signal = [leaf for leaf in leaves if not _is_relaxable(leaf)]
    if not relaxable or not high_signal:
        return None
    return FilterTree.from_flat_and(high_signal)


# An ordered broadening rung: the filters and retriever to try for one pass.
_BroadeningStep = tuple[FilterTree | None, RetrieverType | None]


def _broadening_ladder(filters: FilterTree | None) -> list[_BroadeningStep]:
    """Build the ordered broadening rungs for an empty filtered search.

    1. RELAXED — keep the high-signal exact filters, drop loose text filters (only if useful).
    2. drop all filters, HYBRID — keyword-match identifiers before pure semantics.
    3. drop all filters, SEMANTIC — pure semantic ranking as the last resort.
    """
    reduced = _high_signal_filters(filters)
    relaxed_rung: list[_BroadeningStep] = [(reduced, None)] if reduced is not None else []
    return relaxed_rung + [
        (None, RetrieverType.HYBRID),
        (None, RetrieverType.SEMANTIC),
    ]


async def _attempt_query(
    filters: FilterTree | None,
    retriever: RetrieverType | None,
    *,
    entity_type: EntityType,
    query_text: str,
    limit: int,
    db_session: WrappedSession,
) -> tuple[SearchResponse, SelectQuery] | None:
    """Run one broadening pass with the given filters/retriever; return it (with its query) only if it produced rows.

    ``retriever`` is resolved through ``_effective_retriever`` so embedding-based strategies
    degrade to fuzzy when embeddings are unavailable. A ValueError means the embedding could
    not be generated for an explicit override — treat it as "no help" so the caller advances
    to the next rung.
    """
    query = SelectQuery(
        entity_type=entity_type,
        query_text=query_text,
        filters=filters,
        retriever=_effective_retriever(retriever),
        limit=limit,
    )
    try:
        response = await engine.execute_search(query, db_session)
    except ValueError as exc:
        logger.debug("Broadening attempt unavailable", retriever=retriever, error=str(exc))
        return None
    return (response, query) if response.results else None


async def _run_broadening_fallback(
    *,
    filters: FilterTree | None,
    entity_type: EntityType,
    query_text: str,
    limit: int,
    db_session: WrappedSession,
    passes: int,
) -> tuple[SearchResponse, SelectQuery] | None:
    """Try up to ``passes`` broadening rungs, returning the first that produced rows.

    Broadens progressively: first relax the loose text filters while keeping the high-signal
    exact filters, then drop all filters and rank by HYBRID, then SEMANTIC. ``passes == 0``
    disables broadening entirely.
    """
    for step_filters, step_retriever in _broadening_ladder(filters)[:passes]:
        result = await _attempt_query(
            step_filters,
            step_retriever,
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
    """Run the structured pass, then broaden progressively when it returns zero rows.

    The number of broadening passes is governed by ``effort``: HIGH=3, MEDIUM=1, LOW=0.
    Broadening first relaxes the loose text filters while keeping the high-signal exact
    filters, then drops all filters and ranks by HYBRID, then SEMANTIC. Returns
    ``(response, executed_query, fallback_used)`` where ``executed_query`` is the query that
    produced the returned rows (the broadened one when ``fallback_used``) so the caller can
    persist it for export/pagination.
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

    fallback = await _run_broadening_fallback(
        filters=query.filters,
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

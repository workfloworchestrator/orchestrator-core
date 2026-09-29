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

When a filtered search returns nothing, broaden the filters progressively so the user still
gets the closest matches instead of an empty result, without discarding the high-signal part
of the query: first relax only the loose text filters while keeping the exact id/status/
customer filters, then drop all filters. The ranking strategy never changes: the hybrid
retriever fuses the fuzzy and the semantic ranking, so with an embedding an empty result can
only mean the filters matched no candidates, and switching retrievers cannot help. A caller
that wants an exact answer turns broadening off with ``allow_fallback=False``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.filters import FilterTree, PathFilter, StringFilter
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.query.results import SearchResponse


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


def _broadening_ladder(filters: FilterTree | None) -> list[FilterTree | None]:
    """Build the ordered broadening rungs (the filters to try per pass) for an empty filtered search.

    1. RELAXED — keep the high-signal exact filters, drop loose text filters (only if useful).
    2. drop all filters.

    An unfiltered search has nothing to broaden: its ladder is empty.
    """
    if filters is None:
        return []
    reduced = _high_signal_filters(filters)
    relaxed_rung: list[FilterTree | None] = [reduced] if reduced is not None else []
    return relaxed_rung + [None]


async def _run_broadening_fallback(
    exact: SelectQuery, query_embedding: list[float] | None, db_session: AsyncSession
) -> tuple[SearchResponse, SelectQuery] | None:
    """Climb the broadening ladder, returning the first rung that produced rows (with its query).

    A rung is the exact query with looser filters: the retriever is unchanged and the query
    embedding of the exact pass is reused, so the query text is embedded once.
    """
    for step_filters in _broadening_ladder(exact.filters):
        query = exact.model_copy(update={"filters": step_filters})
        response = await engine.execute_search(query, db_session, query_embedding=query_embedding)
        if response.results:
            return response, query
    return None


async def execute_search_with_fallback(
    *,
    entity_type: EntityType,
    query_text: str | None,
    filters: FilterTree | None,
    limit: int,
    retriever: RetrieverType | None,
    allow_fallback: bool,
    db_session: AsyncSession,
) -> tuple[SearchResponse, SelectQuery, bool]:
    """Run the exact pass, then broaden the filters progressively when it returns zero rows.

    Broadening first relaxes the loose text filters while keeping the high-signal exact
    filters, then drops all filters; the retriever stays as requested and the query embedding
    of the exact pass is reused. ``allow_fallback=False`` disables broadening. Returns
    ``(response, executed_query, fallback_used)`` where ``executed_query`` is the query that
    produced the returned rows (the broadened one when ``fallback_used``) so the caller can
    persist it for export/pagination.
    """
    query = SelectQuery(
        entity_type=entity_type,
        query_text=query_text,
        filters=filters,
        limit=limit,
        # A retriever only ranks free text; without any there is nothing for it to override.
        retriever=retriever if query_text else None,
    )
    response = await engine.execute_search(query, db_session)

    # Results found, broadening not wanted, or nothing to rank a broader set on (no free text).
    if response.results or not allow_fallback or not query_text:
        return response, query, False

    fallback = await _run_broadening_fallback(query, response.query_embedding, db_session)
    if fallback is None:
        return response, query, False

    fb_response, fb_query = fallback
    return fb_response, fb_query, True

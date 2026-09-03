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

"""The semantic retriever against a real pgvector database, bounded plan and exhaustive plan."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType, RetrieverType
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.builder import build_candidate_query
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.base import HNSW_ITERATIVE_SCAN
from orchestrator.core.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.core.settings import llm_settings

DIMENSION = llm_settings.EMBEDDING_DIMENSION
ENTITY_TYPES = ("SUBSCRIPTION", "PRODUCT", "WORKFLOW", "PROCESS")


def _basis_vector(index: int) -> list[float]:
    """Unit vector along one axis, so distances between them are known and equal."""
    return [1.0 if i == index else 0.0 for i in range(DIMENSION)]


def _index_row(entity_id: UUID, path: str, value: str, title: str, embedding: list[float] | None) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        entity_title=title,
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
        embedding=embedding,
    )


@pytest.fixture
def indexed_vectors() -> list[UUID]:
    """Four subscriptions whose descriptions sit at increasing distance from `_basis_vector(0)`."""
    ids = [uuid4() for _ in range(4)]
    rows = []
    for rank, entity_id in enumerate(ids):
        # Blending in the query's own axis makes each entity strictly closer than the next.
        weight = 1.0 - rank * 0.2
        embedding = [weight if i == 0 else (1.0 - weight if i == rank + 1 else 0.0) for i in range(DIMENSION)]
        rows.append(_index_row(entity_id, "subscription.description", f"description {rank}", f"sub {rank}", embedding))
        # A second, far field per entity, so the window has to spread across entities.
        rows.append(
            _index_row(entity_id, "subscription.note", f"note {rank}", f"sub {rank}", _basis_vector(100 + rank))
        )
    db.session.add_all(rows)
    db.session.commit()
    return ids


def _semantic_query(limit: int = 10) -> SelectQuery:
    return SelectQuery(
        entity_type=EntityType.SUBSCRIPTION,
        query_text="description",
        retriever=RetrieverType.SEMANTIC,
        limit=limit,
    )


def _run(retriever: SemanticRetriever, query) -> list[str]:
    stmt = retriever.apply(build_candidate_query(query))
    return [str(row.entity_id) for row in db.session.execute(stmt).mappings().all()]


def test_migration_creates_a_partial_hnsw_index_per_entity_type():
    """Without the per-type index the scan walks other types' vectors and can return nothing."""
    definitions = dict(
        db.session.execute(
            text(
                "select indexname, indexdef from pg_indexes where tablename = 'ai_search_index' and indexdef ilike '%hnsw%'"
            )
        ).all()
    )

    assert set(definitions) == {f"ix_flat_embed_hnsw_{t.lower()}" for t in ENTITY_TYPES}, (
        "one per type, shared one dropped"
    )
    for entity_type in ENTITY_TYPES:
        assert f"entity_type = '{entity_type}'" in definitions[f"ix_flat_embed_hnsw_{entity_type.lower()}"]


def test_bounded_and_exhaustive_plans_agree(indexed_vectors):
    """The window is an approximation of the full ranking, not a different ranking."""
    query = _semantic_query()
    bounded = SemanticRetriever(_basis_vector(0), None, EntityType.SUBSCRIPTION, candidates_limit=100)
    exhaustive = SemanticRetriever(_basis_vector(0), None, candidates_limit=None)

    assert _run(bounded, query) == _run(exhaustive, query) == [str(i) for i in indexed_vectors]


async def test_search_applies_the_iterative_scan_setting(indexed_vectors, async_session):
    """Without it the index scan stops at roughly ef_search rows, short of the window size."""
    response = await engine.execute_search(_semantic_query(), async_session, query_embedding=_basis_vector(0))

    # The async test session is joined to db.session's connection, so the setting is visible there.
    applied = db.session.execute(text(f"select current_setting('{HNSW_ITERATIVE_SCAN.name}', true)")).scalar_one()
    assert applied == HNSW_ITERATIVE_SCAN.value, "the setting must still be live on the search transaction"
    assert [r.entity_id for r in response.results] == [str(i) for i in indexed_vectors]


async def _page_through(query, session, max_pages: int = 10) -> tuple[list[str], list[bool]]:
    """Walk keyset pages the way the endpoint does, with the +1 fetch deciding `has_more`."""
    seen: list[str] = []
    has_more: list[bool] = []
    cursor = None
    for _ in range(max_pages):
        response = await engine.execute_search(query, session, cursor, query_embedding=_basis_vector(0))
        seen.extend(r.entity_id for r in response.results)
        has_more.append(response.has_more)
        assert len(response.results) <= query.limit
        if not response.has_more:
            break
        last = response.results[-1]
        cursor = PageCursor(score=float(last.score), id=last.entity_id, query_id=uuid4())
    return seen, has_more


async def test_keyset_pagination_walks_the_window_without_gaps_or_repeats(indexed_vectors, async_session):
    """Every page recomputes the same window, so cursors stay consistent across pages."""
    seen, has_more = await _page_through(_semantic_query(limit=3), async_session)

    assert seen == [str(i) for i in indexed_vectors]
    assert has_more == [True, False]


async def test_pagination_stops_at_the_edge_of_the_window(indexed_vectors, async_session, monkeypatch):
    """Past the window there is nothing to page into: `has_more` turns false rather than returning gaps."""
    monkeypatch.setattr(llm_settings, "SEARCH_SEMANTIC_CANDIDATE_LIMIT", 2)

    seen, has_more = await _page_through(_semantic_query(limit=1), async_session)

    assert seen == [str(i) for i in indexed_vectors[:2]]
    assert has_more == [True, False]

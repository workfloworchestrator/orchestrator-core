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

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import aliased

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchEmbedding, AiSearchIndex
from orchestrator.core.search.core.types import BooleanOperator, EntityType, FilterOp, RetrieverType, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.builder import build_candidate_query
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.core.search.retrieval.session import HNSW_ITERATIVE_SCAN
from orchestrator.core.settings import llm_settings
from test.integration_tests.search._embeddings import add_indexed_row
from test.integration_tests.search.performance._plans import plan_nodes, plan_of_statement
from test.integration_tests.search.retrieval._semantic_dataset import (
    BOUNDED_CANDIDATES_LIMIT,
    QUERIES,
    SNAPSHOT_DIMENSION,
    embed,
    seed_corpus,
)

DIMENSION = llm_settings.EMBEDDING_DIMENSION
ENTITY_TYPES = ("SUBSCRIPTION", "PRODUCT", "WORKFLOW", "PROCESS")
SNAPSHOT = Path(__file__).parent / "semantic_scores.json"


def _basis_vector(index: int) -> list[float]:
    """Unit vector along one axis, so distances between them are known and equal."""
    return [1.0 if i == index else 0.0 for i in range(DIMENSION)]


def _add_row(entity_id: UUID, path: str, value: str, title: str, embedding: list[float] | None) -> None:
    add_indexed_row(
        db.session,
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        path=path,
        value=value,
        embedding=embedding,
        title=title,
    )


@pytest.fixture
def indexed_vectors() -> list[UUID]:
    """Four subscriptions whose descriptions sit at increasing distance from `_basis_vector(0)`."""
    ids = [uuid4() for _ in range(4)]
    for rank, entity_id in enumerate(ids):
        # Blending in the query's own axis makes each entity strictly closer than the next.
        weight = 1.0 - rank * 0.2
        embedding = [weight if i == 0 else (1.0 - weight if i == rank + 1 else 0.0) for i in range(DIMENSION)]
        _add_row(entity_id, "subscription.description", f"description {rank}", f"sub {rank}", embedding)
        # A second, far field per entity, so the window has to spread across entities.
        _add_row(entity_id, "subscription.note", f"note {rank}", f"sub {rank}", _basis_vector(100 + rank))
    db.session.commit()
    return ids


def _semantic_query(limit: int = 10, filters: FilterTree | None = None) -> SelectQuery:
    return SelectQuery(
        entity_type=EntityType.SUBSCRIPTION,
        query_text="description",
        retriever=RetrieverType.SEMANTIC,
        limit=limit,
        filters=filters,
    )


def _description_is(value: str) -> FilterTree:
    """The filter shape production sends: a path leaf that becomes a correlated EXISTS on entity_id."""
    return FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="subscription.description",
                condition=EqualityFilter(op=FilterOp.EQ, value=value),
                value_kind=UIType.STRING,
            )
        ],
    )


def _run(retriever: SemanticRetriever, query) -> list[str]:
    stmt = retriever.apply(build_candidate_query(query))
    return [str(row.entity_id) for row in db.session.execute(stmt).mappings().all()]


def test_migration_creates_a_partial_hnsw_index_per_entity_type():
    """Without the per-type index the scan walks other types' vectors and can return nothing."""
    definitions = dict(
        db.session.execute(
            text(
                "select indexname, indexdef from pg_indexes where tablename = 'ai_search_embeddings' and indexdef ilike '%hnsw%'"
            )
        ).all()
    )

    assert set(definitions) == {f"ix_ai_search_embeddings_hnsw_{t.lower()}" for t in ENTITY_TYPES}, (
        "one per type, shared one dropped"
    )
    for entity_type in ENTITY_TYPES:
        assert f"entity_type = '{entity_type}'" in definitions[f"ix_ai_search_embeddings_hnsw_{entity_type.lower()}"]


def test_orphan_embedding_does_not_take_a_place_in_the_window(indexed_vectors):
    """An embeddings row that no index row points at must not take a place in the window.

    The orphan is the nearest vector, so in a window of two it would leave one entity to rank.
    """
    query_vector = _basis_vector(0)
    query_vector[5] = 0.05
    db.session.add(AiSearchEmbedding(entity_type="SUBSCRIPTION", embedding_hash="orphan", embedding=query_vector))
    db.session.commit()
    retriever = SemanticRetriever(query_vector, None, EntityType.SUBSCRIPTION, candidates_limit=2)

    assert _run(retriever, _semantic_query()) == [str(i) for i in indexed_vectors[:2]]


def test_bounded_and_exhaustive_plans_agree(indexed_vectors):
    """The window is an approximation of the full ranking, not a different ranking."""
    query = _semantic_query()
    bounded = SemanticRetriever(_basis_vector(0), None, EntityType.SUBSCRIPTION, candidates_limit=100)
    exhaustive = SemanticRetriever(_basis_vector(0), None, candidates_limit=None)

    assert _run(bounded, query) == _run(exhaustive, query) == [str(i) for i in indexed_vectors]


def test_filtered_candidate_query_uses_bounded_plan(indexed_vectors):
    """A production filter is an entity predicate, it must land inside the window, not be dropped by the guard."""
    candidate_query = build_candidate_query(_semantic_query(filters=_description_is("description 1")))
    retriever = SemanticRetriever(_basis_vector(0), None, EntityType.SUBSCRIPTION, candidates_limit=100)

    stmt = retriever.apply(candidate_query)
    results = db.session.execute(stmt).mappings().all()

    assert "semantic_candidates" in str(stmt)
    assert [row.entity_id for row in results] == [indexed_vectors[1]]


def test_joined_candidate_query_uses_exhaustive_plan(indexed_vectors):
    filter_row = aliased(AiSearchIndex)
    candidate_query = (
        select(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        .join(filter_row, filter_row.entity_id == AiSearchIndex.entity_id)
        .where(filter_row.value == "description 1")
        .distinct()
    )
    retriever = SemanticRetriever(_basis_vector(0), None, EntityType.SUBSCRIPTION, candidates_limit=100)

    stmt = retriever.apply(candidate_query)
    results = db.session.execute(stmt).mappings().all()

    assert "semantic_candidates" not in str(stmt)
    assert [row.entity_id for row in results] == [indexed_vectors[1]]


def test_grouped_candidate_query_uses_exhaustive_plan():
    candidate_query = (
        select(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        .where(AiSearchIndex.entity_type == EntityType.SUBSCRIPTION.value)
        .distinct()
        .group_by(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        .having(func.count() > 1)
    )
    retriever = SemanticRetriever(_basis_vector(0), None, EntityType.SUBSCRIPTION, candidates_limit=100)

    assert "semantic_candidates" not in str(retriever.apply(candidate_query))


@pytest.mark.benchmark
async def test_search_applies_the_iterative_scan_setting(indexed_vectors, async_session):
    """Without it the index scan stops at roughly ef_search rows, short of the window size."""
    response = await engine.execute_search(_semantic_query(), async_session, query_embedding=_basis_vector(0))

    # The async test session is joined to db.session's connection, so the setting is visible there.
    applied = db.session.execute(text(f"select current_setting('{HNSW_ITERATIVE_SCAN.name}', true)")).scalar_one()
    assert applied == HNSW_ITERATIVE_SCAN.value, "the setting must still be live on the search transaction"
    assert [r.entity_id for r in response.results] == [str(i) for i in indexed_vectors]


async def test_pagination_stops_at_the_edge_of_the_window(indexed_vectors, async_session, monkeypatch):
    """Past the window there is nothing to page into: `has_more` turns false rather than returning gaps."""
    monkeypatch.setattr(llm_settings, "SEARCH_SEMANTIC_CANDIDATE_LIMIT", 2)
    query = _semantic_query(limit=1)

    first = await engine.execute_search(query, async_session, query_embedding=_basis_vector(0))
    last = first.results[-1]
    cursor = PageCursor(score=float(last.score), id=last.entity_id, query_id=uuid4())
    second = await engine.execute_search(query, async_session, cursor, query_embedding=_basis_vector(0))

    assert [result.entity_id for result in first.results] == [str(indexed_vectors[0])]
    assert first.has_more is True
    assert [result.entity_id for result in second.results] == [str(indexed_vectors[1])]
    assert second.has_more is False


def _scores(candidates_limit: int | None, query_text: str) -> list[tuple[str, float]]:
    """The retriever's ranking of the corpus for a query, as `(entity_id, score)` in ranking order."""
    query = SelectQuery(
        entity_type=EntityType.SUBSCRIPTION, query_text=query_text, retriever=RetrieverType.SEMANTIC, limit=100
    )
    retriever = SemanticRetriever(embed(query_text), None, EntityType.SUBSCRIPTION, candidates_limit=candidates_limit)
    rows = db.session.execute(retriever.apply(build_candidate_query(query))).mappings().all()
    return [(str(row["entity_id"]), float(row["score"])) for row in rows]


@pytest.mark.skipif(
    DIMENSION != SNAPSHOT_DIMENSION,
    reason=f"semantic_scores.json was recorded with EMBEDDING_DIMENSION={SNAPSHOT_DIMENSION}, the vectors of the "
    "corpus depend on it",
)
@pytest.mark.parametrize(
    "candidates_limit",
    [pytest.param(None, id="unbounded"), pytest.param(BOUNDED_CANDIDATES_LIMIT, id="bounded")],
)
@pytest.mark.parametrize("query_text", [pytest.param(query, id=query.replace(" ", "_")) for query in QUERIES])
def test_semantic_scores_match_snapshot(query_text, candidates_limit):
    """Every entity keeps the score the exhaustive plan gave it in `semantic_scores.json`, on either plan.

    A query missing from the file is recorded and fails once. To re-record, delete its entry and rerun.
    """
    seed_corpus(db.session)
    db.session.commit()
    ranking = _scores(candidates_limit, query_text)

    recorded = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    if query_text not in recorded:
        SNAPSHOT.write_text(json.dumps({**recorded, query_text: dict(ranking)}, indent=2, sort_keys=True) + "\n")
        pytest.fail(f"Recorded the scores of {query_text!r} in {SNAPSHOT.name}, review and commit them, then rerun")

    assert dict(ranking) == pytest.approx(recorded[query_text], abs=1e-6)
    assert [score for _, score in ranking] == sorted((score for _, score in ranking), reverse=True)


COMMON_TEXT_ROWS = 30
TEXTS_IN_WINDOW = 4


def test_common_text_does_not_fill_window():
    """The window counts distinct texts, so a text shared by many entities takes one place, not one per row.

    Here 30 rows share the nearest text and the window of 4 texts still reaches the other 3 entities.
    """
    common = [uuid4() for _ in range(COMMON_TEXT_ROWS)]
    others = [uuid4() for _ in range(5)]
    for entity_id in common:  # a side effect per row, not a collection that is built
        _add_row(entity_id, "subscription.status", "active", "common", _basis_vector(0))
    for rank, entity_id in enumerate(others):  # a side effect per row, not a collection that is built
        weight = 0.9 - rank * 0.1
        embedding = [weight if i == 0 else (1.0 - weight if i == rank + 1 else 0.0) for i in range(DIMENSION)]
        _add_row(entity_id, "subscription.description", f"description {rank}", f"other {rank}", embedding)
    db.session.commit()
    retriever = SemanticRetriever(_basis_vector(0), None, EntityType.SUBSCRIPTION, candidates_limit=TEXTS_IN_WINDOW)

    ranked = _run(retriever, _semantic_query(limit=100))

    assert ranked == sorted(str(i) for i in common) + [str(i) for i in others[: TEXTS_IN_WINDOW - 1]]


@pytest.mark.parametrize("entity_type", [pytest.param(EntityType(t), id=t.lower()) for t in ENTITY_TYPES])
def test_each_entity_type_uses_own_hnsw_index(entity_type):
    """The type is a literal in the window's scan so the planner can prove the partial index predicate.

    A bound parameter would leave a sort that reads every vector of the type.
    """
    for rank in range(3):  # a side effect per row, not a collection that is built
        add_indexed_row(
            db.session,
            entity_type=entity_type,
            entity_id=uuid4(),
            path=f"{entity_type.value.lower()}.description",
            value=f"description {rank}",
            embedding=_basis_vector(rank),
        )
    db.session.commit()
    # With a few rows a sequential scan and a sort is cheaper, the question here is only whether the index is usable.
    db.session.execute(text("SET LOCAL enable_seqscan = off"))
    db.session.execute(text("SET LOCAL enable_sort = off"))
    query = SelectQuery(entity_type=entity_type, query_text="description", retriever=RetrieverType.SEMANTIC)
    retriever = SemanticRetriever(_basis_vector(0), None, entity_type, candidates_limit=10)

    plan = plan_of_statement(retriever.apply(build_candidate_query(query)))

    assert (f"ix_ai_search_embeddings_hnsw_{entity_type.value.lower()}", "ai_search_embeddings") in {
        (node.get("Index Name"), node.get("Relation Name")) for node in plan_nodes(plan)
    }

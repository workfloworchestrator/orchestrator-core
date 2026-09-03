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

"""Tests for the hybrid retriever as a union of a fuzzy and a semantic candidate source.

Seeds a small index with deterministic embeddings (unit vectors on distinct axes) so vector
distances are controllable, and checks ranking, the perfect-match flag, highlights, filters,
the transaction-local HNSW setting and pagination through both the retriever and the engine.
"""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType, FilterOp, SearchMetadata, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.builder import build_candidate_query
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.base import SessionSetting
from orchestrator.core.search.retrieval.retrievers.hybrid import RrfHybridRetriever
from orchestrator.core.settings import llm_settings

EXACT_DESCRIPTION = "Node Peering asd066d-jnp-02"
SIBLING_DESCRIPTION = "Node Peering asd066d-jnp-03"  # word_similarity 0.93 against EXACT_DESCRIPTION: also >= 0.9
SEMANTIC_DESCRIPTION = "Corelink Amsterdam Groningen"
TERMINATED_DESCRIPTION = "Peering asd066d-jnp-09 spare"  # word_similarity 0.75 against EXACT_DESCRIPTION
NO_TRIGRAM_QUERY = "backbone capacity upgrade"  # trigram-matches none of the seeded values
TYPO_QUERY = "Node Peering asd077d-jnp-03"  # sibling 0.75, exact 0.69, nothing else passes the 0.6 gate
EMBEDDER = "orchestrator.core.search.core.embedding.QueryEmbedder.generate_for_text_async"


def _vec(axis: int) -> list[float]:
    vector = [0.0] * llm_settings.EMBEDDING_DIMENSION
    vector[axis] = 1.0
    return vector


def _index_row(
    entity_id: UUID, path: str, value: str, title: str, embedding: list[float] | None = None
) -> AiSearchIndex:
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


class Seeded:
    """Ids of the seeded subscriptions and the embedding axis of each description."""

    exact = uuid4()
    sibling = uuid4()
    semantic_only = uuid4()
    terminated = uuid4()
    referrer = uuid4()  # carries EXACT_DESCRIPTION in a nested block field, not in its own description
    axes = {exact: 1, sibling: 2, semantic_only: 0, terminated: 3, referrer: 4}


@pytest.fixture
def seeded() -> type[Seeded]:
    rows = [
        _index_row(Seeded.exact, "subscription.description", EXACT_DESCRIPTION, "exact", _vec(1)),
        # a weaker sibling field that also passes the trigram gate (0.71) and would drag an average down
        _index_row(Seeded.exact, "subscription.port.node.title", "Node asd066d-jnp-02", "exact"),
        _index_row(Seeded.exact, "subscription.status", "active", "exact"),
        _index_row(Seeded.sibling, "subscription.description", SIBLING_DESCRIPTION, "sibling", _vec(2)),
        _index_row(Seeded.sibling, "subscription.status", "active", "sibling"),
        _index_row(Seeded.semantic_only, "subscription.description", SEMANTIC_DESCRIPTION, "semantic", _vec(0)),
        _index_row(Seeded.semantic_only, "subscription.status", "active", "semantic"),
        _index_row(Seeded.terminated, "subscription.description", TERMINATED_DESCRIPTION, "terminated", _vec(3)),
        _index_row(Seeded.terminated, "subscription.status", "terminated", "terminated"),
        _index_row(Seeded.referrer, "subscription.description", "IP Peer referrer", "referrer", _vec(4)),
        _index_row(
            Seeded.referrer,
            "subscription.ip_peer_block.peers.0.peer_group.title",
            EXACT_DESCRIPTION,
            "referrer",
            _vec(4),
        ),
        _index_row(Seeded.referrer, "subscription.status", "active", "referrer"),
    ]
    db.session.add_all(rows)
    db.session.commit()
    return Seeded


def _active_filter() -> FilterTree:
    return FilterTree.from_flat_and(
        [
            PathFilter(
                path="subscription.status",
                condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            )
        ]
    )


def _run_retriever(query_text: str, q_vec: list[float], filters: FilterTree | None = None, limit: int = 10) -> list:
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query_text, filters=filters, limit=limit)
    retriever = RrfHybridRetriever(q_vec, query_text, cursor=None, entity_type=EntityType.SUBSCRIPTION)
    stmt = retriever.apply(build_candidate_query(query)).limit(limit)
    return list(db.session.execute(stmt).mappings().all())


# ---------------------------------------------------------------------------
# Retriever-level ranking
# ---------------------------------------------------------------------------


def test_exact_match_ranks_first_and_is_perfect_despite_weaker_sibling_field(seeded):
    """The flag uses the best field: the 0.71 node title does not drag the 1.0 description below 0.9."""
    rows = _run_retriever(EXACT_DESCRIPTION, _vec(seeded.axes[seeded.exact]))

    assert [r["entity_id"] for r in rows[:3]] == [seeded.exact, seeded.referrer, seeded.sibling]
    assert [r["perfect_match"] for r in rows[:3]] == [1, 1, 1]
    assert rows[0]["highlight_path"] == "subscription.description"
    assert rows[0]["highlight_text"] == EXACT_DESCRIPTION


def test_entity_itself_outranks_entity_referencing_the_same_text(seeded):
    """Equal fuzzy scores: the shallower matching path wins, and a semantic edge cannot flip a perfect match.

    The referrer carries the exact text in a nested field and gets the closest embedding here; the
    subscription whose own description matches must still come first.
    """
    rows = _run_retriever(EXACT_DESCRIPTION, _vec(seeded.axes[seeded.referrer]))

    assert [r["entity_id"] for r in rows[:2]] == [seeded.exact, seeded.referrer]
    assert rows[1]["highlight_path"] == "subscription.ip_peer_block.peers.0.peer_group.title"


def test_entity_without_trigram_hit_is_still_ranked_semantically(seeded):
    """No field trigram-matches the phrase, so results come from the semantic source alone."""
    rows = _run_retriever(NO_TRIGRAM_QUERY, _vec(seeded.axes[seeded.semantic_only]))

    assert rows[0]["entity_id"] == seeded.semantic_only
    assert rows[0]["highlight_path"] == "subscription.description"
    assert rows[0]["highlight_text"] == SEMANTIC_DESCRIPTION
    assert {r["perfect_match"] for r in rows} == {0}
    # Every embedded entity is present (every seeded description carries an embedding)
    assert {r["entity_id"] for r in rows} == set(seeded.axes)


def test_fuzzy_only_hits_appear_below_perfect_matches(seeded):
    """The terminated subscription trigram-matches (0.75) but is not perfect; it still shows up."""
    rows = _run_retriever(EXACT_DESCRIPTION, _vec(seeded.axes[seeded.exact]))

    by_id = {r["entity_id"]: r for r in rows}
    assert by_id[seeded.terminated]["perfect_match"] == 0
    assert float(by_id[seeded.terminated]["score"]) < float(by_id[seeded.sibling]["score"])


def test_entity_in_both_sources_outranks_single_source_entities(seeded):
    """Typo query: sibling wins on fuzzy rank 1 + semantic rank 1.

    Exact (fuzzy rank 2 + semantic rank 2) still ranks above entities present in only one source.
    """
    rows = _run_retriever(TYPO_QUERY, _vec(seeded.axes[seeded.sibling]))

    order = [r["entity_id"] for r in rows]
    assert order[:2] == [seeded.sibling, seeded.exact]
    assert {r["perfect_match"] for r in rows} == {0}
    by_id = {r["entity_id"]: r for r in rows}
    assert float(by_id[seeded.semantic_only]["score"]) < float(by_id[seeded.exact]["score"])


def test_structured_filter_removes_entity_from_both_sources(seeded):
    """A filtered-out entity is absent even though it trigram-matches and has an embedding."""
    rows = _run_retriever(EXACT_DESCRIPTION, _vec(seeded.axes[seeded.terminated]), filters=_active_filter())

    assert seeded.terminated not in {r["entity_id"] for r in rows}
    assert rows[0]["entity_id"] == seeded.exact


# ---------------------------------------------------------------------------
# Engine-level behaviour
# ---------------------------------------------------------------------------


async def test_engine_routes_multi_word_text_to_hybrid(seeded):
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=EXACT_DESCRIPTION, limit=10)

    with patch(EMBEDDER, return_value=_vec(seeded.axes[seeded.exact])):
        response = await engine.execute_search(query, db.session)

    assert response.metadata == SearchMetadata.hybrid()
    first = response.results[0]
    assert first.entity_id == str(seeded.exact)
    assert first.perfect_match == 1
    assert first.matching_fields[0].path == "subscription.description"
    assert first.matching_fields[0].highlight_indices == [(0, 4), (5, 12), (13, 27)]


async def test_engine_plain_language_returns_semantic_results(seeded):
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=NO_TRIGRAM_QUERY, limit=10)

    with patch(EMBEDDER, return_value=_vec(seeded.axes[seeded.semantic_only])):
        response = await engine.execute_search(query, db.session)

    assert response.metadata == SearchMetadata.hybrid()
    assert response.results[0].entity_id == str(seeded.semantic_only)
    assert (
        response.results[0].matching_fields[0].highlight_indices is None
        or response.results[0].matching_fields[0].highlight_indices == []
    )


async def test_engine_falls_back_to_fuzzy_without_embedding(seeded):
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=EXACT_DESCRIPTION, limit=10)

    with patch(EMBEDDER, return_value=None):
        response = await engine.execute_search(query, db.session)

    assert response.metadata == SearchMetadata.fuzzy()
    # The fuzzy retriever has no depth tiebreak: the entity itself and the referrer both score 1.0
    top_two = response.results[:2]
    assert {r.entity_id for r in top_two} == {str(seeded.exact), str(seeded.referrer)}
    assert all(r.score == pytest.approx(1.0) for r in top_two)


async def test_engine_applies_iterative_scan_for_the_transaction(seeded):
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=EXACT_DESCRIPTION, limit=10)

    with patch(EMBEDDER, return_value=_vec(seeded.axes[seeded.exact])):
        await engine.execute_search(query, db.session)

    setting = db.session.execute(text("select current_setting('hnsw.iterative_scan', true)")).scalar()
    assert setting == "relaxed_order"


async def test_engine_pagination_continues_after_cursor(seeded):
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=EXACT_DESCRIPTION, limit=2)
    q_vec = _vec(seeded.axes[seeded.exact])

    with patch(EMBEDDER, return_value=q_vec):
        first_page = await engine.execute_search(query, db.session)
        last = first_page.results[-1]
        cursor = PageCursor(score=last.score, id=last.entity_id, query_id=uuid4())
        second_page = await engine.execute_search(query, db.session, cursor=cursor, query_embedding=q_vec)

    assert first_page.has_more is True
    assert len(first_page.results) == 2
    first_ids = {r.entity_id for r in first_page.results}
    assert first_ids == {str(seeded.exact), str(seeded.referrer)}
    assert all(r.entity_id not in first_ids for r in second_page.results)
    assert all(r.score <= last.score for r in second_page.results)
    assert len(second_page.results) == 2


async def test_engine_skips_a_setting_the_database_rejects(seeded):
    """An unknown ``hnsw.*`` name must not abort the search transaction; other settings still apply.

    That is what pgvector < 0.8 says about ``hnsw.iterative_scan`` once the library is loaded.
    """
    # Load the pgvector library in this backend so the reserved-prefix check raises an ERROR, not a WARNING.
    db.session.execute(text("select '[0]'::vector"))
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=EXACT_DESCRIPTION, limit=10)
    settings = (SessionSetting("hnsw.does_not_exist", "x"), SessionSetting("hnsw.iterative_scan", "relaxed_order"))

    with (
        patch(EMBEDDER, return_value=_vec(seeded.axes[seeded.exact])),
        patch.object(RrfHybridRetriever, "session_settings", new_callable=lambda: property(lambda self: settings)),
    ):
        response = await engine.execute_search(query, db.session)

    assert response.results[0].entity_id == str(seeded.exact)
    assert db.session.execute(text("select current_setting('hnsw.iterative_scan', true)")).scalar() == "relaxed_order"

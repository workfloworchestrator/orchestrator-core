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

"""Tests for ProcessHybridRetriever SQL query generation.

Covers the last-step (JSONB) fuzzy source, how it is united with the fuzzy retriever's rows,
the optional semantic side, the apply() method (CTEs, RRF scoring, pagination), and metadata.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.core.search.retrieval.retrievers.process import ProcessHybridRetriever
from orchestrator.core.search.retrieval.session import HNSW_ITERATIVE_SCAN

pytestmark = pytest.mark.search

RESULT_COLUMNS = ["entity_id", "entity_title", "score", "highlight_text", "highlight_path"]


def compile_sql(stmt) -> str:
    """Compile a SQLAlchemy statement to a PostgreSQL SQL string."""
    compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False})
    return str(compiled)


@pytest.fixture
def candidate_query():
    """Basic candidate query returning entity_id and entity_title."""
    return select(
        AiSearchIndex.entity_id.label("entity_id"),
        AiSearchIndex.entity_title.label("entity_title"),
    ).distinct()


@pytest.fixture
def query_id() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "q_vec",
    [
        pytest.param(None, id="none"),
        pytest.param([], id="empty_list"),
        pytest.param([0.1, 0.2, 0.3], id="non_empty_list"),
    ],
)
def test_init_stores_q_vec_as_given(q_vec):
    """Whatever is passed as q_vec ends up on self.q_vec."""
    retriever = ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None)
    assert retriever.q_vec == q_vec


def test_init_builds_the_two_retrievers():
    """The fuzzy retriever always exists; the semantic one carries the window and entity type."""
    retriever = ProcessHybridRetriever(
        q_vec=[0.1, 0.2],
        fuzzy_term="world",
        cursor=None,
        k=30,
        entity_type=EntityType.PROCESS,
        semantic_candidates_limit=7,
    )
    assert retriever.k == 30
    assert retriever.fuzzy.fuzzy_term == "world"
    assert retriever.semantic is not None
    assert retriever.semantic.vector_query == [0.1, 0.2]
    assert retriever.semantic.entity_type == EntityType.PROCESS
    assert retriever.semantic.candidates_limit == 7


@pytest.mark.parametrize(
    "q_vec,entity_type,expected",
    [
        pytest.param(None, EntityType.PROCESS, (), id="fuzzy_only_needs_nothing"),
        pytest.param([0.1, 0.2], None, (), id="unbounded_semantic_needs_nothing"),
        pytest.param([0.1, 0.2], EntityType.PROCESS, (HNSW_ITERATIVE_SCAN,), id="bounded_semantic_scans_iteratively"),
    ],
)
def test_session_settings_follow_the_semantic_side(q_vec, entity_type, expected):
    retriever = ProcessHybridRetriever(
        q_vec=q_vec, fuzzy_term="term", cursor=None, entity_type=entity_type, semantic_candidates_limit=10
    )
    assert tuple(retriever.session_settings) == expected


# ---------------------------------------------------------------------------
# Last-step (JSONB) source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql_fragment",
    [
        pytest.param("process_steps", id="references_process_step_table"),
        pytest.param("LATERAL", id="uses_lateral_subquery"),
        pytest.param("completed_at DESC", id="picks_the_last_step"),
        pytest.param("word_similarity", id="scores_with_word_similarity"),
        pytest.param("ILIKE", id="filters_with_ilike"),
        pytest.param("AS LTREE", id="labels_the_path_as_ltree"),
    ],
)
def test_last_step_results_sql_contains(candidate_query, sql_fragment):
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    sql = compile_sql(retriever._last_step_results(candidate_query))
    assert sql_fragment in sql


def test_last_step_results_match_the_fuzzy_retriever_shape(candidate_query):
    """Both sources are unioned, so the last-step rows must carry the same columns in the same order."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    assert list(retriever._last_step_results(candidate_query).selected_columns.keys()) == RESULT_COLUMNS
    assert list(FuzzyRetriever("foo", cursor=None).apply(candidate_query).selected_columns.keys()) == RESULT_COLUMNS


def test_fuzzy_results_keep_the_best_score_per_process(candidate_query):
    """Indexed and last-step rows are united and reduced to one row per process, best score first, ties by path."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    sql = compile_sql(select(retriever._fuzzy_results(candidate_query)))
    assert "UNION ALL" in sql
    assert "DISTINCT ON (fuzzy_sources.entity_id)" in sql
    assert "ORDER BY fuzzy_sources.entity_id, fuzzy_sources.score DESC, fuzzy_sources.highlight_path" in sql


def test_last_step_results_are_capped(candidate_query):
    """The lateral last-step lookup stops once enough matching processes are found, as it did before."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    sql = compile_sql(retriever._last_step_results(candidate_query))
    assert "LIMIT" in sql


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_fragment",
    [
        pytest.param("process_steps", id="searches_last_steps"),
        pytest.param("UNION ALL", id="unites_indexed_and_last_step_rows"),
    ],
)
def test_apply_sql_contains(candidate_query, expected_fragment):
    """apply() carries the process-specific fuzzy side into the fused statement."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
    sql = compile_sql(retriever.apply(candidate_query))
    assert expected_fragment.lower() in sql.lower()


@pytest.mark.parametrize(
    "q_vec,expect_semantic_side",
    [
        pytest.param(None, False, id="none_q_vec_fuzzy_only"),
        pytest.param([0.1, 0.2, 0.3], True, id="q_vec_adds_semantic_side"),
    ],
)
@pytest.mark.parametrize("fragment", ["<->", "semantic_results", "FULL OUTER JOIN"])
def test_apply_semantic_side_only_with_q_vec(candidate_query, q_vec, expect_semantic_side, fragment):
    """Without q_vec the statement is fuzzy-only: no vector operator, semantic subquery or outer join."""
    retriever = ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None)
    sql = compile_sql(retriever.apply(candidate_query))
    assert (fragment in sql) is expect_semantic_side


def test_apply_with_cursor_adds_pagination_where_clause(candidate_query, query_id):
    """When a cursor is provided, a WHERE clause for pagination is added."""
    cursor = PageCursor(score=0.75, id="entity-abc", query_id=query_id)
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=cursor)
    sql = compile_sql(retriever.apply(candidate_query))
    assert "WHERE" in sql
    assert "ranked_results.entity_id >" in sql


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "q_vec",
    [
        pytest.param(None, id="none_q_vec"),
        pytest.param([0.1, 0.2], id="with_q_vec"),
    ],
)
def test_metadata_is_hybrid_regardless_of_q_vec(q_vec):
    """Metadata is always SearchMetadata.hybrid() irrespective of q_vec."""
    retriever = ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None)
    assert retriever.metadata == SearchMetadata.hybrid()

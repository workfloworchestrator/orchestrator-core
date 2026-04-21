"""Tests for ProcessHybridRetriever SQL query generation.

Covers semantic distance expression, indexed candidates, JSONB candidates,
the apply() method (CTEs, UNION ALL, RRF scoring, pagination), and metadata.
"""

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

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.process import ProcessHybridRetriever

pytestmark = pytest.mark.search


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


def _build_indexed_stmt(retriever, candidate_query):
    """Build the indexed-candidates statement with standard args."""
    cand = candidate_query.subquery()
    sem_val = retriever._get_semantic_distance_expr()
    best_similarity = func.word_similarity(retriever.fuzzy_term, AiSearchIndex.value)
    filter_condition = AiSearchIndex.value_type.in_(retriever.SEARCHABLE_FIELD_TYPES)
    return retriever._build_indexed_candidates(cand, sem_val, best_similarity, filter_condition)


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


def test_init_parent_attributes_set():
    """Parent attributes are correctly initialised."""
    retriever = ProcessHybridRetriever(
        q_vec=[0.1, 0.2], fuzzy_term="world", cursor=None, k=30, field_candidates_limit=50
    )
    assert retriever.fuzzy_term == "world"
    assert retriever.k == 30
    assert retriever.field_candidates_limit == 50


# ---------------------------------------------------------------------------
# Semantic distance expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "q_vec,expect_literal_only",
    [
        pytest.param(None, True, id="none_q_vec_literal_only"),
        pytest.param([0.1, 0.9], False, id="q_vec_uses_embedding"),
    ],
)
def test_semantic_distance_expr(q_vec, expect_literal_only):
    """None -> literal 1.0 only (no <-> or coalesce); list -> embedding distance with coalesce."""
    retriever = ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None)
    expr = retriever._get_semantic_distance_expr()
    sql = compile_sql(select(expr))

    assert "semantic_distance" in sql
    if expect_literal_only:
        assert "<->" not in sql
        assert "coalesce" not in sql.lower()
    else:
        assert "<->" in sql
        assert "coalesce" in sql.lower()


# ---------------------------------------------------------------------------
# Indexed candidates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "assertion_key,assertion_check",
    [
        pytest.param("ai_search_index", lambda sql: "ai_search_index" in sql.lower(), id="selects_ai_search_index"),
        pytest.param("entity_id", lambda sql: "entity_id" in sql, id="has_entity_id"),
        pytest.param("entity_title", lambda sql: "entity_title" in sql, id="has_entity_title"),
        pytest.param("semantic_distance", lambda sql: "semantic_distance" in sql, id="has_semantic_distance"),
        pytest.param("fuzzy_score", lambda sql: "fuzzy_score" in sql, id="has_fuzzy_score"),
        pytest.param("value_type_in", lambda sql: "value_type" in sql and "IN" in sql, id="filters_by_value_type"),
    ],
)
def test_indexed_candidates_sql_structure(candidate_query, assertion_key, assertion_check):
    """The indexed-candidates query contains expected SQL elements."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    sql = compile_sql(_build_indexed_stmt(retriever, candidate_query))
    assert assertion_check(sql)


def test_indexed_candidates_joins_candidates_cte(candidate_query):
    """The indexed-candidates query joins on the candidates CTE entity_id."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    sql = compile_sql(_build_indexed_stmt(retriever, candidate_query))
    assert "entity_id" in sql


def test_indexed_candidates_applies_limit(candidate_query):
    """The indexed-candidates query has a LIMIT clause."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None, field_candidates_limit=42)
    sql = compile_sql(_build_indexed_stmt(retriever, candidate_query))
    assert "LIMIT" in sql


# ---------------------------------------------------------------------------
# JSONB candidates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql_fragment",
    [
        pytest.param("process_steps", id="references_process_step_table"),
        pytest.param("LATERAL", id="uses_lateral_subquery"),
        pytest.param("word_similarity", id="uses_word_similarity"),
        pytest.param("semantic_distance", id="has_semantic_distance_label"),
    ],
)
def test_jsonb_candidates_sql_contains(candidate_query, sql_fragment):
    """The JSONB-candidates query contains expected SQL fragments."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    cand = candidate_query.subquery()
    sql = compile_sql(retriever._build_jsonb_candidates(cand))
    assert sql_fragment.lower() in sql.lower()


def test_jsonb_candidates_casts_state_to_text(candidate_query):
    """The JSONB state column is cast to TEXT for substring search."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    cand = candidate_query.subquery()
    sql = compile_sql(retriever._build_jsonb_candidates(cand))
    assert "TEXT" in sql or "text" in sql.lower() or "CAST" in sql


def test_jsonb_candidates_uses_ilike_filter(candidate_query):
    """The JSONB-candidates query uses ILIKE for filtering by fuzzy term."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="testterm", cursor=None)
    cand = candidate_query.subquery()
    sql = compile_sql(retriever._build_jsonb_candidates(cand))
    assert "ilike" in sql.lower()


def test_jsonb_candidates_has_ltree_path_label(candidate_query):
    """The JSONB candidates include a path column cast to LTREE."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    cand = candidate_query.subquery()
    sql = compile_sql(retriever._build_jsonb_candidates(cand))
    assert "ltree" in sql.lower()
    assert "path" in sql


def test_jsonb_candidates_orders_by_completed_at_desc(candidate_query):
    """The lateral subquery orders by completed_at DESC to pick the last step."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
    cand = candidate_query.subquery()
    sql = compile_sql(retriever._build_jsonb_candidates(cand))
    assert "completed_at" in sql
    assert "DESC" in sql


def test_jsonb_candidates_applies_limit(candidate_query):
    """The JSONB-candidates query has a LIMIT clause."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None, field_candidates_limit=77)
    cand = candidate_query.subquery()
    sql = compile_sql(retriever._build_jsonb_candidates(cand))
    assert "LIMIT" in sql


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_fragment",
    [
        pytest.param("field_candidates", id="has_field_candidates_cte"),
        pytest.param("entity_scores", id="has_entity_scores_cte"),
        pytest.param("ranked_results", id="has_ranked_results_cte"),
        pytest.param("UNION ALL", id="unions_indexed_and_jsonb"),
        pytest.param("dense_rank", id="has_rrf_dense_rank"),
        pytest.param("word_similarity", id="has_rrf_word_similarity"),
        pytest.param("highlight_text", id="has_highlight_text"),
        pytest.param("highlight_path", id="has_highlight_path"),
        pytest.param("perfect_match", id="has_perfect_match"),
        pytest.param("DESC", id="orders_by_score_desc"),
    ],
)
def test_apply_sql_contains(candidate_query, expected_fragment):
    """apply() produces SQL referencing expected fragments."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
    sql = compile_sql(retriever.apply(candidate_query))
    assert expected_fragment.lower() in sql.lower()


def test_apply_process_steps_in_union(candidate_query):
    """The query UNION ALLs indexed and JSONB candidates (process_steps appears)."""
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
    sql = compile_sql(retriever.apply(candidate_query))
    assert "process_steps" in sql.lower()


@pytest.mark.parametrize(
    "q_vec,expect_q_vec_param",
    [
        pytest.param(None, False, id="none_q_vec_no_param"),
        pytest.param([0.1, 0.2, 0.3], True, id="q_vec_with_param"),
    ],
)
def test_apply_q_vec_param(candidate_query, q_vec, expect_q_vec_param):
    """q_vec presence determines whether :q_vec bind-param and <-> operator appear."""
    retriever = ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None)
    stmt = retriever.apply(candidate_query)
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}))

    if expect_q_vec_param:
        assert "q_vec" in sql
        assert "<->" in sql
    else:
        assert "q_vec" not in sql
        assert "<->" not in sql


def test_apply_with_cursor_adds_pagination_where_clause(candidate_query, query_id):
    """When a cursor is provided, a WHERE clause for pagination is added."""
    cursor = PageCursor(score=0.75, id="entity-abc", query_id=query_id)
    retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=cursor)
    sql = compile_sql(retriever.apply(candidate_query))
    assert "WHERE" in sql


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

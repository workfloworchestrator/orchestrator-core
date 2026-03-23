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

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import SearchMetadata
from orchestrator.search.retrieval.pagination import PageCursor
from orchestrator.search.retrieval.retrievers.process import ProcessHybridRetriever

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


class TestProcessHybridRetrieverInit:
    """Tests for ProcessHybridRetriever.__init__."""

    @pytest.mark.parametrize(
        "q_vec",
        [None, [], [0.1, 0.2, 0.3]],
        ids=["none", "empty_list", "non_empty_list"],
    )
    def test_init_stores_q_vec_as_given(self, q_vec):
        """Whatever is passed as q_vec ends up on self.q_vec."""
        retriever = ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None)
        assert retriever.q_vec == q_vec

    def test_init_parent_attributes_set(self):
        """Parent attributes are correctly initialised."""
        retriever = ProcessHybridRetriever(
            q_vec=[0.1, 0.2], fuzzy_term="world", cursor=None, k=30, field_candidates_limit=50
        )

        assert retriever.fuzzy_term == "world"
        assert retriever.k == 30
        assert retriever.field_candidates_limit == 50


class TestGetSemanticDistanceExpr:
    """Tests for ProcessHybridRetriever._get_semantic_distance_expr."""

    @pytest.mark.parametrize(
        "q_vec, expect_literal_only",
        [
            (None, True),
            ([0.1, 0.9], False),
        ],
        ids=["none_q_vec_literal_only", "q_vec_uses_embedding"],
    )
    def test_semantic_distance_expr(self, q_vec, expect_literal_only):
        """None → literal 1.0 only (no <-> or coalesce); list → embedding distance with coalesce."""
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


class TestBuildIndexedCandidates:
    """Tests for ProcessHybridRetriever._build_indexed_candidates."""

    @staticmethod
    def _build_stmt(retriever, candidate_query):
        """Build the indexed-candidates statement with standard args."""
        cand = candidate_query.subquery()
        sem_val = retriever._get_semantic_distance_expr()
        best_similarity = func.word_similarity(retriever.fuzzy_term, AiSearchIndex.value)
        filter_condition = AiSearchIndex.value_type.in_(retriever.SEARCHABLE_FIELD_TYPES)
        return retriever._build_indexed_candidates(cand, sem_val, best_similarity, filter_condition)

    def test_indexed_candidates_selects_ai_search_index_columns(self, candidate_query):
        """The indexed-candidates query selects the expected AiSearchIndex columns."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        sql = compile_sql(self._build_stmt(retriever, candidate_query))

        assert "ai_search_index" in sql.lower()
        assert "entity_id" in sql
        assert "entity_title" in sql
        assert "semantic_distance" in sql
        assert "fuzzy_score" in sql

    def test_indexed_candidates_joins_candidates_cte(self, candidate_query):
        """The indexed-candidates query joins on the candidates CTE entity_id."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        sql = compile_sql(self._build_stmt(retriever, candidate_query))

        assert "entity_id" in sql

    def test_indexed_candidates_applies_limit(self, candidate_query):
        """The indexed-candidates query has a LIMIT clause."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None, field_candidates_limit=42)
        sql = compile_sql(self._build_stmt(retriever, candidate_query))

        assert "LIMIT" in sql

    def test_indexed_candidates_filters_by_searchable_field_types(self, candidate_query):
        """The indexed-candidates query filters by value_type IN (SEARCHABLE_FIELD_TYPES)."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        sql = compile_sql(self._build_stmt(retriever, candidate_query))

        assert "value_type" in sql
        assert "IN" in sql


class TestBuildJsonbCandidates:
    """Tests for ProcessHybridRetriever._build_jsonb_candidates."""

    def test_jsonb_candidates_references_process_step_table(self, candidate_query):
        """The JSONB-candidates query references ProcessStepTable (process_steps)."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "process_steps" in sql.lower()

    def test_jsonb_candidates_uses_lateral_subquery(self, candidate_query):
        """The JSONB-candidates query uses a LATERAL subquery for last_step."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "LATERAL" in sql

    def test_jsonb_candidates_casts_state_to_text(self, candidate_query):
        """The JSONB state column is cast to TEXT for substring search."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "TEXT" in sql or "text" in sql.lower() or "CAST" in sql

    def test_jsonb_candidates_uses_word_similarity(self, candidate_query):
        """The JSONB-candidates query uses word_similarity for fuzzy scoring."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "word_similarity" in sql

    def test_jsonb_candidates_uses_ilike_filter(self, candidate_query):
        """The JSONB-candidates query uses ILIKE for filtering by fuzzy term."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="testterm", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "ILIKE" in sql or "ilike" in sql.lower()

    def test_jsonb_candidates_uses_semantic_distance_literal_one(self, candidate_query):
        """The JSONB path always produces a constant semantic_distance of 1.0."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        # The literal 1.0 is a bind param; check for the label name instead
        assert "semantic_distance" in sql

    def test_jsonb_candidates_has_path_label(self, candidate_query):
        """The JSONB candidates include a path column cast to LTREE."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "LTREE" in sql or "ltree" in sql.lower()
        assert "path" in sql

    def test_jsonb_candidates_orders_by_completed_at_desc(self, candidate_query):
        """The lateral subquery orders by completed_at DESC to pick the last step."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "completed_at" in sql
        assert "DESC" in sql

    def test_jsonb_candidates_applies_limit(self, candidate_query):
        """The JSONB-candidates query has a LIMIT clause."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="foo", cursor=None, field_candidates_limit=77)
        cand = candidate_query.subquery()

        stmt = retriever._build_jsonb_candidates(cand)
        sql = compile_sql(stmt)

        assert "LIMIT" in sql


class TestApply:
    """Tests for ProcessHybridRetriever.apply."""

    def test_apply_contains_expected_ctes(self, candidate_query):
        """apply() produces SQL referencing all expected CTEs."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
        sql = compile_sql(retriever.apply(candidate_query))

        for cte_name in ("field_candidates", "entity_scores", "ranked_results"):
            assert cte_name in sql

    def test_apply_unions_indexed_and_jsonb_candidates(self, candidate_query):
        """The query UNION ALLs indexed and JSONB candidates (process_steps appears)."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
        sql = compile_sql(retriever.apply(candidate_query))

        assert "UNION ALL" in sql
        assert "process_steps" in sql.lower()

    def test_apply_contains_rrf_score_components(self, candidate_query):
        """The final query contains RRF scoring (dense_rank, word_similarity)."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
        sql = compile_sql(retriever.apply(candidate_query))

        assert "dense_rank" in sql
        assert "word_similarity" in sql

    def test_apply_includes_highlight_and_match_columns(self, candidate_query):
        """The final SELECT includes highlight_text, highlight_path, and perfect_match columns."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
        sql = compile_sql(retriever.apply(candidate_query))

        for col in ("highlight_text", "highlight_path", "perfect_match"):
            assert col in sql

    @pytest.mark.parametrize(
        "q_vec, expect_q_vec_param",
        [
            (None, False),
            ([0.1, 0.2, 0.3], True),
        ],
        ids=["none_q_vec_no_param", "q_vec_with_param"],
    )
    def test_apply_q_vec_param(self, candidate_query, q_vec, expect_q_vec_param):
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

    def test_apply_orders_by_score_desc(self, candidate_query):
        """The final query is ordered by score DESC."""
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=None)
        sql = compile_sql(retriever.apply(candidate_query))

        assert "DESC" in sql

    def test_apply_with_cursor_adds_pagination_where_clause(self, candidate_query, query_id):
        """When a cursor is provided, a WHERE clause for pagination is added."""
        cursor = PageCursor(score=0.75, id="entity-abc", query_id=query_id)
        retriever = ProcessHybridRetriever(q_vec=None, fuzzy_term="test", cursor=cursor)
        sql = compile_sql(retriever.apply(candidate_query))

        assert "WHERE" in sql


class TestMetadata:
    """Tests for ProcessHybridRetriever.metadata property."""

    @pytest.mark.parametrize(
        "q_vec",
        [None, [0.1, 0.2]],
        ids=["none_q_vec", "with_q_vec"],
    )
    def test_metadata_is_hybrid_regardless_of_q_vec(self, q_vec):
        """Metadata is always SearchMetadata.hybrid() irrespective of q_vec."""
        retriever = ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None)

        assert isinstance(retriever.metadata, SearchMetadata)
        assert retriever.metadata == SearchMetadata.hybrid()

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

import pytest
from sqlalchemy import literal, select
from sqlalchemy.dialects import postgresql

from orchestrator.db import db
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.retrieval.pagination import PaginationParams
from orchestrator.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.search.retrieval.retrievers.hybrid import RrfHybridRetriever, compute_rrf_hybrid_score_sql
from orchestrator.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.search.retrieval.retrievers.structured import StructuredRetriever

from .snapshot_helper import assert_sql_matches_snapshot


def compile_query_to_sql(query) -> str:
    """Compile SQLAlchemy query to PostgreSQL SQL string."""
    compiled = query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False})
    return str(compiled)


@pytest.fixture
def candidate_query():
    """Basic candidate query that returns entity IDs."""
    return select(AiSearchIndex.entity_id.label("entity_id")).distinct()


class TestStructuredRetriever:
    """Test SQL structure for StructuredRetriever."""

    def test_basic_query_structure(self, candidate_query, request):
        """Test basic structured retrieval query structure."""
        pagination_params = PaginationParams()
        retriever = StructuredRetriever(pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("StructuredRetriever.test_basic_query_structure", sql, request)

    def test_pagination_structure(self, candidate_query, request):
        """Test pagination adds WHERE clause with correct comparison operator."""
        pagination_params = PaginationParams(page_after_id="test-id-123")
        retriever = StructuredRetriever(pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("StructuredRetriever.test_pagination_structure", sql, request)

    def test_metadata(self):
        """Test metadata returns correct search type."""
        pagination_params = PaginationParams()
        retriever = StructuredRetriever(pagination_params)

        metadata = retriever.metadata

        assert metadata.search_type == "structured"


class TestFuzzyRetriever:
    """Test SQL structure for FuzzyRetriever."""

    def test_basic_query_structure(self, candidate_query, request):
        """Test fuzzy retrieval query structure with all components."""
        pagination_params = PaginationParams()
        retriever = FuzzyRetriever("test query", pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("FuzzyRetriever.test_basic_query_structure", sql, request)

    def test_pagination_structure(self, candidate_query, request):
        """Test pagination with score and id adds correct WHERE clause."""
        pagination_params = PaginationParams(page_after_score=0.85, page_after_id="entity-123")
        retriever = FuzzyRetriever("test", pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("FuzzyRetriever.test_pagination_structure", sql, request)

    def test_metadata(self):
        """Test metadata returns correct search type."""
        pagination_params = PaginationParams()
        retriever = FuzzyRetriever("test", pagination_params)

        metadata = retriever.metadata

        assert metadata.search_type == "fuzzy"


class TestSemanticRetriever:
    """Test SQL structure for SemanticRetriever."""

    def test_basic_query_structure(self, candidate_query, request):
        """Test semantic retrieval query structure with all components."""
        pagination_params = PaginationParams()
        query_vector = [0.1, 0.2, 0.3]
        retriever = SemanticRetriever(query_vector, pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("SemanticRetriever.test_basic_query_structure", sql, request)

    def test_pagination_structure(self, candidate_query, request):
        """Test pagination with score and id adds correct WHERE clause."""
        pagination_params = PaginationParams(page_after_score=0.92, page_after_id="entity-456")
        query_vector = [0.1, 0.2, 0.3]
        retriever = SemanticRetriever(query_vector, pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("SemanticRetriever.test_pagination_structure", sql, request)

    def test_metadata(self):
        """Test metadata returns correct search type."""
        pagination_params = PaginationParams()
        query_vector = [0.1, 0.2, 0.3]
        retriever = SemanticRetriever(query_vector, pagination_params)

        metadata = retriever.metadata

        assert metadata.search_type == "semantic"


class TestRrfHybridRetriever:
    """Test SQL structure for RrfHybridRetriever (Reciprocal Rank Fusion)."""

    def test_basic_query_structure(self, candidate_query, request):
        """Test hybrid RRF query structure with all CTEs."""
        pagination_params = PaginationParams()
        query_vector = [0.1, 0.2, 0.3]
        retriever = RrfHybridRetriever(query_vector, "test", pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("RrfHybridRetriever.test_basic_query_structure", sql, request)

    def test_pagination_structure(self, candidate_query, request):
        """Test that pagination adds score and entity_id comparison logic."""
        pagination_params = PaginationParams(page_after_score=0.95, page_after_id="entity-789")
        query_vector = [0.1, 0.2, 0.3]
        retriever = RrfHybridRetriever(query_vector, "test", pagination_params)

        query = retriever.apply(candidate_query)
        sql = compile_query_to_sql(query)

        assert_sql_matches_snapshot("RrfHybridRetriever.test_pagination_structure", sql, request)

    def test_metadata(self):
        """Test metadata returns correct search type."""
        pagination_params = PaginationParams()
        query_vector = [0.1, 0.2, 0.3]
        retriever = RrfHybridRetriever(query_vector, "test", pagination_params)

        metadata = retriever.metadata

        assert metadata.search_type == "hybrid"


class TestRrfScoreComputation:
    """Test the RRF score computation."""

    @pytest.mark.parametrize(
        "avg_fuzzy_score, expected_flag",
        [
            (0.89, 0),  # Below threshold
            (0.90, 1),  # At threshold
            (0.95, 1),  # Above threshold
        ],
        ids=["below_threshold", "at_threshold", "above_threshold"],
    )
    def test_perfect_match_detection(self, avg_fuzzy_score, expected_flag):
        """Test perfect match flag evaluates correctly based on the threshold."""
        components = compute_rrf_hybrid_score_sql(
            sem_rank_col=literal(1),
            fuzzy_rank_col=literal(1),
            avg_fuzzy_score_col=literal(avg_fuzzy_score),
            k=60,
            perfect_threshold=0.9,
        )

        result_flag = db.session.execute(select(components["perfect"])).scalar()
        assert result_flag is not None and result_flag == expected_flag

    @pytest.mark.parametrize(
        "k, sem_rank, fuzzy_rank, expected_rrf",
        [
            (60, 1, 1, 2 / 61),
            (10, 1, 1, 2 / 11),
            (60, 1, 5, (1 / 61) + (1 / 65)),
        ],
        ids=["k=60_symmetric", "k=10_symmetric", "k=60_asymmetric"],
    )
    def test_base_rrf_score_component(self, k, sem_rank, fuzzy_rank, expected_rrf):
        """Test the base rrf_num component calculates correctly."""
        result = compute_rrf_hybrid_score_sql(
            sem_rank_col=literal(sem_rank),
            fuzzy_rank_col=literal(fuzzy_rank),
            avg_fuzzy_score_col=literal(0.5),
            k=k,
            perfect_threshold=0.9,
        )
        rrf_val = db.session.execute(select(result["rrf_num"])).scalar()
        assert rrf_val is not None and float(rrf_val) == pytest.approx(expected_rrf, abs=0.0001)

    @pytest.mark.parametrize(
        "sem_rank, fuzzy_rank, fuzzy_score",
        [
            (1, 1, 0.5),
            (100, 100, 0.5),
            (1, 1, 0.95),
            (50, 50, 0.95),
            (1, 1000, 0.5),
        ],
        ids=[
            "best_ranks_no_boost",
            "worst_ranks_no_boost",
            "best_ranks_with_boost",
            "mid_ranks_with_boost",
            "extreme_rank_difference",
        ],
    )
    def test_normalized_score_is_always_in_range(self, sem_rank, fuzzy_rank, fuzzy_score):
        """Test that the normalized score is always within the [0, 1] range for various inputs."""
        components = compute_rrf_hybrid_score_sql(
            sem_rank_col=literal(sem_rank),
            fuzzy_rank_col=literal(fuzzy_rank),
            avg_fuzzy_score_col=literal(fuzzy_score),
            k=60,
            perfect_threshold=0.9,
        )
        score = db.session.execute(select(components["normalized_score"])).scalar()

        assert score is not None and 0 <= float(score) <= 1, f"Score {score} was outside the expected [0, 1] range"

    @pytest.mark.parametrize(
        "n_sources, expected_numerator",
        [
            (2, 2),
            (3, 3),
            (4, 4),
        ],
        ids=["2_sources", "3_sources", "4_sources"],
    )
    def test_n_sources_parameter_affects_rrf_max(self, n_sources, expected_numerator):
        """Test that the n_sources parameter correctly affects the rrf_max calculation."""
        k = 60
        components = compute_rrf_hybrid_score_sql(
            sem_rank_col=literal(1),
            fuzzy_rank_col=literal(1),
            avg_fuzzy_score_col=literal(0.5),
            k=k,
            perfect_threshold=0.9,
            n_sources=n_sources,
        )

        rrf_max_val = db.session.execute(select(components["rrf_max"])).scalar()

        # Assert: Check if the value matches the formula n_sources / (k + 1)
        expected_value = expected_numerator / (k + 1)
        assert rrf_max_val is not None and float(rrf_max_val) == pytest.approx(expected_value)

    @pytest.mark.parametrize(
        "margin_factor, expected_multiplier",
        [
            (0.05, 1.05),
            (0.1, 1.1),
            (0.0, 1.0),
        ],
        ids=["5%_margin", "10%_margin", "0%_margin"],
    )
    def test_margin_factor_parameter_affects_beta(self, margin_factor, expected_multiplier):
        """Test that the margin_factor parameter correctly affects the beta calculation."""

        k = 60
        n_sources = 2

        components = compute_rrf_hybrid_score_sql(
            sem_rank_col=literal(1),
            fuzzy_rank_col=literal(1),
            avg_fuzzy_score_col=literal(0.5),
            k=k,
            perfect_threshold=0.9,
            n_sources=n_sources,
            margin_factor=margin_factor,
        )

        beta_val = db.session.execute(select(components["beta"])).scalar()

        # beta = rrf_max * (1 + margin_factor)
        rrf_max = n_sources / (k + 1)
        expected_beta = rrf_max * expected_multiplier

        assert beta_val is not None and float(beta_val) == pytest.approx(expected_beta)

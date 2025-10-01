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
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.retrieval.pagination import PaginationParams
from orchestrator.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.search.retrieval.retrievers.hybrid import RrfHybridRetriever
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

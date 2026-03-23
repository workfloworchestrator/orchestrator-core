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

from unittest.mock import MagicMock

import pytest

from orchestrator.search.core.types import EntityType
from orchestrator.search.retrieval.retrievers.base import Retriever
from orchestrator.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.search.retrieval.retrievers.hybrid import RrfHybridRetriever
from orchestrator.search.retrieval.retrievers.process import ProcessHybridRetriever
from orchestrator.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.search.retrieval.retrievers.structured import StructuredRetriever

pytestmark = pytest.mark.search

EMBEDDING = [0.1, 0.2, 0.3]
FUZZY_TERM = "my search"
QUERY_TEXT = "full query text"


def _make_query(
    fuzzy_term: str | None = None,
    entity_type: EntityType = EntityType.SUBSCRIPTION,
    vector_query: object = None,
    query_text: str | None = None,
) -> MagicMock:
    query = MagicMock()
    query.fuzzy_term = fuzzy_term
    query.entity_type = entity_type
    query.vector_query = vector_query
    query.query_text = query_text
    query.order_by = None
    return query


# ---------------------------------------------------------------------------
# Parameterised routing table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fuzzy_term,entity_type,query_embedding,vector_query,query_text,expected_type",
    [
        # Hybrid (embedding + fuzzy) → RrfHybridRetriever
        (FUZZY_TERM, EntityType.SUBSCRIPTION, EMBEDDING, None, None, RrfHybridRetriever),
        # Hybrid + PROCESS entity → ProcessHybridRetriever
        (FUZZY_TERM, EntityType.PROCESS, EMBEDDING, None, None, ProcessHybridRetriever),
        # Semantic only (embedding, no fuzzy) → SemanticRetriever
        (None, EntityType.SUBSCRIPTION, EMBEDDING, None, None, SemanticRetriever),
        # Fuzzy only → FuzzyRetriever
        (FUZZY_TERM, EntityType.SUBSCRIPTION, None, None, None, FuzzyRetriever),
        # Fuzzy + PROCESS → ProcessHybridRetriever (None embedding, fuzzy_term set)
        (FUZZY_TERM, EntityType.PROCESS, None, None, None, ProcessHybridRetriever),
        # No text/embedding → StructuredRetriever
        (None, EntityType.SUBSCRIPTION, None, None, None, StructuredRetriever),
        # Embedding failed fallback: query_embedding=None, vector_query set, query_text set
        # → fuzzy_term reassigned to query_text → FuzzyRetriever
        (None, EntityType.SUBSCRIPTION, None, MagicMock(), QUERY_TEXT, FuzzyRetriever),
        # Embedding failed fallback + PROCESS → ProcessHybridRetriever
        (None, EntityType.PROCESS, None, MagicMock(), QUERY_TEXT, ProcessHybridRetriever),
    ],
)
def test_retriever_routing(
    fuzzy_term: str | None,
    entity_type: EntityType,
    query_embedding: list[float] | None,
    vector_query: object,
    query_text: str | None,
    expected_type: type,
) -> None:
    query = _make_query(
        fuzzy_term=fuzzy_term,
        entity_type=entity_type,
        vector_query=vector_query,
        query_text=query_text,
    )
    cursor = None

    retriever = Retriever.route(query, cursor, query_embedding=query_embedding)

    assert isinstance(retriever, expected_type)


# ---------------------------------------------------------------------------
# Additional assertions on constructed retriever attributes
# ---------------------------------------------------------------------------


class TestRetrieverRoutingAttributes:
    def test_rrf_hybrid_carries_embedding_and_fuzzy_term(self) -> None:
        query = _make_query(fuzzy_term=FUZZY_TERM)
        retriever = Retriever.route(query, cursor=None, query_embedding=EMBEDDING)

        assert isinstance(retriever, RrfHybridRetriever)

    def test_semantic_carries_embedding(self) -> None:
        query = _make_query()
        retriever = Retriever.route(query, cursor=None, query_embedding=EMBEDDING)

        assert isinstance(retriever, SemanticRetriever)
        assert retriever.vector_query == EMBEDDING

    def test_fuzzy_carries_fuzzy_term(self) -> None:
        query = _make_query(fuzzy_term=FUZZY_TERM)
        retriever = Retriever.route(query, cursor=None, query_embedding=None)

        assert isinstance(retriever, FuzzyRetriever)
        assert retriever.fuzzy_term == FUZZY_TERM

    def test_structured_carries_order_by(self) -> None:
        order_by = MagicMock()
        query = _make_query()
        query.order_by = order_by

        retriever = Retriever.route(query, cursor=None, query_embedding=None)

        assert isinstance(retriever, StructuredRetriever)
        assert retriever.order_by is order_by

    def test_embedding_fallback_uses_query_text_as_fuzzy_term(self) -> None:
        query = _make_query(vector_query=MagicMock(), query_text=QUERY_TEXT)
        retriever = Retriever.route(query, cursor=None, query_embedding=None)

        assert isinstance(retriever, FuzzyRetriever)
        assert retriever.fuzzy_term == QUERY_TEXT

    def test_process_hybrid_with_no_embedding_carries_none_embedding(self) -> None:
        query = _make_query(fuzzy_term=FUZZY_TERM, entity_type=EntityType.PROCESS)
        retriever = Retriever.route(query, cursor=None, query_embedding=None)

        assert isinstance(retriever, ProcessHybridRetriever)

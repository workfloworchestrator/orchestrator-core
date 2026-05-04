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

"""Tests for Retriever.route() dispatch logic and constructed retriever attributes.

Verifies that the correct retriever subclass is selected based on the combination
of fuzzy_term, entity_type, query_embedding, and vector_query/query_text inputs,
and that constructed retrievers carry the expected attributes.
"""

from unittest.mock import MagicMock

import pytest

from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.core.search.retrieval.retrievers.hybrid import RrfHybridRetriever
from orchestrator.core.search.retrieval.retrievers.process import ProcessHybridRetriever
from orchestrator.core.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.core.search.retrieval.retrievers.structured import StructuredRetriever

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
    query.retriever = None  # auto-routing; explicit overrides are tested separately
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
        pytest.param(
            FUZZY_TERM, EntityType.SUBSCRIPTION, EMBEDDING, MagicMock(), None, RrfHybridRetriever, id="hybrid"
        ),
        pytest.param(
            FUZZY_TERM, EntityType.PROCESS, EMBEDDING, MagicMock(), None, ProcessHybridRetriever, id="hybrid_process"
        ),
        pytest.param(
            None, EntityType.SUBSCRIPTION, EMBEDDING, MagicMock(), None, SemanticRetriever, id="semantic_only"
        ),
        pytest.param(FUZZY_TERM, EntityType.SUBSCRIPTION, None, None, None, FuzzyRetriever, id="fuzzy_only"),
        pytest.param(FUZZY_TERM, EntityType.PROCESS, None, None, None, ProcessHybridRetriever, id="fuzzy_process"),
        pytest.param(None, EntityType.SUBSCRIPTION, None, None, None, StructuredRetriever, id="structured"),
        pytest.param(
            None, EntityType.SUBSCRIPTION, None, MagicMock(), QUERY_TEXT, FuzzyRetriever, id="embedding_fallback_fuzzy"
        ),
        pytest.param(
            None,
            EntityType.PROCESS,
            None,
            MagicMock(),
            QUERY_TEXT,
            ProcessHybridRetriever,
            id="embedding_fallback_process",
        ),
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
    """Verify the correct retriever subclass is selected for given inputs."""
    query = _make_query(
        fuzzy_term=fuzzy_term,
        entity_type=entity_type,
        vector_query=vector_query,
        query_text=query_text,
    )
    retriever = Retriever.route(query, cursor=None, query_embedding=query_embedding)
    assert isinstance(retriever, expected_type)


# ---------------------------------------------------------------------------
# Constructed retriever attributes
# ---------------------------------------------------------------------------


def test_semantic_carries_embedding() -> None:
    """SemanticRetriever stores the query embedding."""
    query = _make_query(vector_query=MagicMock())
    retriever = Retriever.route(query, cursor=None, query_embedding=EMBEDDING)
    assert isinstance(retriever, SemanticRetriever)
    assert retriever.vector_query == EMBEDDING


def test_fuzzy_carries_fuzzy_term() -> None:
    """FuzzyRetriever stores the fuzzy term."""
    query = _make_query(fuzzy_term=FUZZY_TERM)
    retriever = Retriever.route(query, cursor=None, query_embedding=None)
    assert isinstance(retriever, FuzzyRetriever)
    assert retriever.fuzzy_term == FUZZY_TERM


def test_structured_carries_order_by() -> None:
    """StructuredRetriever stores the order_by from the query."""
    order_by = MagicMock()
    query = _make_query()
    query.order_by = order_by
    retriever = Retriever.route(query, cursor=None, query_embedding=None)
    assert isinstance(retriever, StructuredRetriever)
    assert retriever.order_by is order_by


def test_embedding_fallback_uses_query_text_as_fuzzy_term() -> None:
    """When embedding fails, query_text is used as fuzzy_term for FuzzyRetriever."""
    query = _make_query(vector_query=MagicMock(), query_text=QUERY_TEXT)
    retriever = Retriever.route(query, cursor=None, query_embedding=None)
    assert isinstance(retriever, FuzzyRetriever)
    assert retriever.fuzzy_term == QUERY_TEXT


def test_process_hybrid_with_no_embedding_carries_none_embedding() -> None:
    """ProcessHybridRetriever with no embedding still routes correctly."""
    query = _make_query(fuzzy_term=FUZZY_TERM, entity_type=EntityType.PROCESS)
    retriever = Retriever.route(query, cursor=None, query_embedding=None)
    assert isinstance(retriever, ProcessHybridRetriever)

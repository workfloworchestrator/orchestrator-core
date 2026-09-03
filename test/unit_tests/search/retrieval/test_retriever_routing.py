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

"""Tests for Retriever._plan() / needs_embedding() / route() with real SelectQuery objects.

Verifies which retriever subclass is selected for a given query text, entity type,
embedding availability and explicit override, and that constructed retrievers carry the
expected attributes.
"""

import pytest

from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.query.mixins import StructuredOrderBy
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.core.search.retrieval.retrievers.hybrid import RrfHybridRetriever
from orchestrator.core.search.retrieval.retrievers.process import ProcessHybridRetriever
from orchestrator.core.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.core.search.retrieval.retrievers.structured import StructuredRetriever

pytestmark = pytest.mark.search

EMBEDDING = [0.1, 0.2, 0.3]
SINGLE_WORD = "fiber"
MULTI_WORD = "Node Peering asd066d-jnp-02"
UUID_TEXT = "12345678-1234-1234-1234-123456789abc"


def _query(
    query_text: str | None = None,
    entity_type: EntityType = EntityType.SUBSCRIPTION,
    retriever: RetrieverType | None = None,
) -> SelectQuery:
    return SelectQuery(entity_type=entity_type, query_text=query_text, retriever=retriever)


# ---------------------------------------------------------------------------
# Auto-routing table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query_text,entity_type,query_embedding,expected_type",
    [
        pytest.param(SINGLE_WORD, EntityType.SUBSCRIPTION, EMBEDDING, RrfHybridRetriever, id="single_word_hybrid"),
        pytest.param(MULTI_WORD, EntityType.SUBSCRIPTION, EMBEDDING, RrfHybridRetriever, id="multi_word_hybrid"),
        pytest.param(SINGLE_WORD, EntityType.PROCESS, EMBEDDING, ProcessHybridRetriever, id="process_hybrid"),
        pytest.param(MULTI_WORD, EntityType.PROCESS, EMBEDDING, ProcessHybridRetriever, id="process_multi_word"),
        pytest.param(UUID_TEXT, EntityType.SUBSCRIPTION, None, FuzzyRetriever, id="uuid_fuzzy"),
        pytest.param(UUID_TEXT, EntityType.PROCESS, None, ProcessHybridRetriever, id="uuid_process"),
        pytest.param(None, EntityType.SUBSCRIPTION, None, StructuredRetriever, id="structured"),
        pytest.param(None, EntityType.PROCESS, None, StructuredRetriever, id="structured_process"),
        pytest.param(MULTI_WORD, EntityType.SUBSCRIPTION, None, FuzzyRetriever, id="embedding_fallback_fuzzy"),
        pytest.param(MULTI_WORD, EntityType.PROCESS, None, ProcessHybridRetriever, id="embedding_fallback_process"),
    ],
)
def test_auto_routing(
    query_text: str | None,
    entity_type: EntityType,
    query_embedding: list[float] | None,
    expected_type: type[Retriever],
) -> None:
    """Without an override, any embeddable text routes to hybrid; UUIDs to fuzzy; no text to structured."""
    retriever = Retriever.route(_query(query_text, entity_type), cursor=None, query_embedding=query_embedding)
    assert isinstance(retriever, expected_type)


@pytest.mark.parametrize(
    "query_text,entity_type,retriever_override,expected",
    [
        pytest.param(SINGLE_WORD, EntityType.SUBSCRIPTION, None, True, id="single_word"),
        pytest.param(MULTI_WORD, EntityType.SUBSCRIPTION, None, True, id="multi_word"),
        pytest.param(UUID_TEXT, EntityType.SUBSCRIPTION, None, False, id="uuid"),
        pytest.param(None, EntityType.SUBSCRIPTION, None, False, id="no_text"),
        pytest.param(MULTI_WORD, EntityType.PROCESS, None, True, id="process_multi_word"),
        pytest.param(UUID_TEXT, EntityType.PROCESS, None, False, id="process_uuid"),
        pytest.param(MULTI_WORD, EntityType.PROCESS, RetrieverType.FUZZY, False, id="process_fuzzy_override"),
        pytest.param(UUID_TEXT, EntityType.PROCESS, RetrieverType.HYBRID, True, id="process_hybrid_override_uuid"),
        pytest.param(MULTI_WORD, EntityType.SUBSCRIPTION, RetrieverType.FUZZY, False, id="fuzzy_override"),
        pytest.param(MULTI_WORD, EntityType.SUBSCRIPTION, RetrieverType.SEMANTIC, True, id="semantic_override"),
    ],
)
def test_needs_embedding(
    query_text: str | None, entity_type: EntityType, retriever_override: RetrieverType | None, expected: bool
) -> None:
    assert Retriever.needs_embedding(_query(query_text, entity_type, retriever_override)) is expected


# ---------------------------------------------------------------------------
# Explicit overrides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override,expected_type",
    [
        pytest.param(RetrieverType.FUZZY, FuzzyRetriever, id="fuzzy"),
        pytest.param(RetrieverType.SEMANTIC, SemanticRetriever, id="semantic"),
        pytest.param(RetrieverType.HYBRID, RrfHybridRetriever, id="hybrid"),
    ],
)
def test_explicit_override_wins(override: RetrieverType, expected_type: type[Retriever]) -> None:
    retriever = Retriever.route(_query(MULTI_WORD, retriever=override), cursor=None, query_embedding=EMBEDDING)
    assert isinstance(retriever, expected_type)


@pytest.mark.parametrize("override", [RetrieverType.SEMANTIC, RetrieverType.HYBRID])
def test_embedding_override_without_embedding_raises(override: RetrieverType) -> None:
    with pytest.raises(ValueError, match="query embedding is not available"):
        Retriever.route(_query(MULTI_WORD, retriever=override), cursor=None, query_embedding=None)


def test_fuzzy_override_needs_no_embedding() -> None:
    retriever = Retriever.route(_query(MULTI_WORD, retriever=RetrieverType.FUZZY), cursor=None, query_embedding=None)
    assert isinstance(retriever, FuzzyRetriever)
    assert retriever.fuzzy_term == MULTI_WORD


# ---------------------------------------------------------------------------
# Constructed retriever attributes
# ---------------------------------------------------------------------------


def test_hybrid_carries_full_query_text_and_embedding() -> None:
    """Hybrid fuzzy-matches on the whole query text, not a single word."""
    retriever = Retriever.route(_query(MULTI_WORD), cursor=None, query_embedding=EMBEDDING)
    assert isinstance(retriever, RrfHybridRetriever)
    assert retriever.fuzzy_term == MULTI_WORD
    assert retriever.q_vec == EMBEDDING
    assert retriever.entity_type == EntityType.SUBSCRIPTION


@pytest.mark.parametrize("entity_type", [EntityType.PRODUCT, EntityType.WORKFLOW, EntityType.PROCESS])
def test_hybrid_carries_entity_type(entity_type: EntityType) -> None:
    """The semantic source restricts the HNSW scan to the queried entity type."""
    retriever = Retriever.route(_query(MULTI_WORD, entity_type), cursor=None, query_embedding=EMBEDDING)
    assert isinstance(retriever, RrfHybridRetriever)
    assert retriever.entity_type == entity_type


def test_semantic_override_carries_embedding() -> None:
    retriever = Retriever.route(
        _query(MULTI_WORD, retriever=RetrieverType.SEMANTIC), cursor=None, query_embedding=EMBEDDING
    )
    assert isinstance(retriever, SemanticRetriever)
    assert retriever.vector_query == EMBEDDING


def test_uuid_fuzzy_carries_query_text() -> None:
    retriever = Retriever.route(_query(UUID_TEXT), cursor=None, query_embedding=None)
    assert isinstance(retriever, FuzzyRetriever)
    assert retriever.fuzzy_term == UUID_TEXT


def test_structured_carries_order_by() -> None:
    order_by = StructuredOrderBy(element="subscription.description")
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, order_by=order_by)
    retriever = Retriever.route(query, cursor=None, query_embedding=None)
    assert isinstance(retriever, StructuredRetriever)
    assert retriever.order_by is order_by


def test_embedding_fallback_uses_query_text_as_fuzzy_term() -> None:
    """When no embedding could be produced, auto-routing degrades to fuzzy on the full text."""
    retriever = Retriever.route(_query(MULTI_WORD), cursor=None, query_embedding=None)
    assert isinstance(retriever, FuzzyRetriever)
    assert retriever.fuzzy_term == MULTI_WORD


def test_process_fallback_carries_none_embedding() -> None:
    retriever = Retriever.route(_query(MULTI_WORD, EntityType.PROCESS), cursor=None, query_embedding=None)
    assert isinstance(retriever, ProcessHybridRetriever)
    assert retriever.q_vec is None
    assert retriever.fuzzy_term == MULTI_WORD
    assert retriever.entity_type == EntityType.PROCESS

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

"""Tests for Retriever.session_settings: which Postgres settings a retriever asks the engine to apply."""

import pytest

from orchestrator.core.search.retrieval.retrievers.base import HNSW_ITERATIVE_SCAN, Retriever, SessionSetting
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.core.search.retrieval.retrievers.hybrid import RrfHybridRetriever
from orchestrator.core.search.retrieval.retrievers.process import ProcessHybridRetriever
from orchestrator.core.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.core.search.retrieval.retrievers.structured import StructuredRetriever

pytestmark = pytest.mark.search

ITERATIVE_SCAN = (SessionSetting("hnsw.iterative_scan", "relaxed_order"),)


@pytest.mark.parametrize(
    "retriever",
    [
        pytest.param(FuzzyRetriever("term", cursor=None), id="fuzzy"),
        pytest.param(SemanticRetriever([0.1, 0.2], cursor=None), id="semantic"),
        pytest.param(StructuredRetriever(None, None, None), id="structured"),
    ],
)
def test_default_session_settings_are_empty(retriever: Retriever) -> None:
    assert retriever.session_settings == ()


def test_hybrid_enables_iterative_hnsw_scan() -> None:
    assert RrfHybridRetriever([0.1, 0.2], "term", cursor=None).session_settings == ITERATIVE_SCAN
    assert HNSW_ITERATIVE_SCAN == SessionSetting(name="hnsw.iterative_scan", value="relaxed_order")


@pytest.mark.parametrize(
    "q_vec,expected",
    [
        pytest.param(None, (), id="fuzzy_only_needs_nothing"),
        pytest.param([0.1, 0.2], ITERATIVE_SCAN, id="with_embedding"),
    ],
)
def test_process_hybrid_only_with_embedding(q_vec: list[float] | None, expected: tuple[SessionSetting, ...]) -> None:
    assert ProcessHybridRetriever(q_vec=q_vec, fuzzy_term="term", cursor=None).session_settings == expected

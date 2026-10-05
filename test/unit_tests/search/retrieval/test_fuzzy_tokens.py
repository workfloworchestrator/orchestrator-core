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

"""How the fuzzy retriever splits a query into independently matched terms."""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever, fuzzy_tokens

pytestmark = pytest.mark.search


@pytest.mark.parametrize(
    "fuzzy_term,expected",
    [
        pytest.param("ACM LIR", ["ACM", "LIR"], id="two-terms"),
        pytest.param("  ACM \t LIR \n", ["ACM", "LIR"], id="surrounding-and-mixed-whitespace"),
        pytest.param("LIR", ["LIR"], id="single-term"),
        pytest.param("ACM acm Acm LIR", ["ACM", "LIR"], id="case-insensitive-duplicates-keep-first"),
        pytest.param("ACM - LIR", ["ACM", "LIR"], id="punctuation-only-term-dropped"),
        pytest.param("192.0.2.0/24", ["192.0.2.0/24"], id="identifier-kept-whole"),
        pytest.param("node01-rtr-01 et-0/0/1", ["node01-rtr-01", "et-0/0/1"], id="identifiers"),
        pytest.param("- / *", ["- / *"], id="no-alphanumeric-term-falls-back-to-whole-query"),
        pytest.param("", [""], id="empty"),
    ],
)
def test_fuzzy_tokens(fuzzy_term, expected):
    assert fuzzy_tokens(fuzzy_term) == expected


@pytest.mark.parametrize(
    "fuzzy_term,gates",
    [
        pytest.param("LIR", 1, id="single-term"),
        pytest.param("ACM LIR", 2, id="two-terms"),
        pytest.param("ACM acm LIR", 2, id="duplicate-term-gated-once"),
    ],
)
def test_every_term_is_scored_and_gated(fuzzy_term, gates):
    """Each term gets its own trigram gate, OR-ed so a field matching any term is a hit."""
    candidates = select(AiSearchIndex.entity_id, AiSearchIndex.entity_title).distinct()
    stmt = FuzzyRetriever(fuzzy_term, cursor=None).apply(candidates)

    sql = str(stmt.compile(dialect=postgresql.dialect()))

    assert sql.count("<%") == gates
    # Each term's best score appears in the SELECT list and again in the HAVING threshold.
    assert sql.count("max(word_similarity(") == 2 * gates
    # The threshold is applied in HAVING, before any highlight is computed.
    assert sql.count("HAVING") == 1
    assert "OVER (" not in sql
    assert "LATERAL" in sql

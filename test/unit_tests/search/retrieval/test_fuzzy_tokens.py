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

"""Query tokenization and trigram filter structure."""

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
    "fuzzy_term",
    [
        pytest.param("LIR", id="single-term"),
        pytest.param("  LIR \t", id="surrounding-whitespace"),
        pytest.param("LIR lir Lir", id="duplicates-collapse-to-one-term"),
        pytest.param("LIR -", id="punctuation-dropped"),
        pytest.param("123e4567-e89b-12d3-a456-426614174000", id="uuid"),
        pytest.param("192.0.2.0/24", id="ip-prefix"),
        pytest.param("- / *", id="punctuation-only"),
        pytest.param("", id="empty"),
    ],
)
def test_single_term_uses_one_direct_gate(fuzzy_term: str) -> None:
    """One unique term needs one trigram filter and no sampling."""
    candidates = select(AiSearchIndex.entity_id, AiSearchIndex.entity_title).distinct()
    stmt = FuzzyRetriever(fuzzy_term, cursor=None).apply(candidates)

    sql = str(stmt.compile(dialect=postgresql.dialect()))

    assert "WITH fuzzy_entities AS MATERIALIZED" in sql
    assert sql.count("<%") == 1
    assert "rarity" not in sql
    assert "EXISTS" not in sql
    assert sql.count("max(word_similarity(") == 2
    assert "HAVING" in sql
    assert "LATERAL" in sql


@pytest.mark.parametrize(
    "fuzzy_term,gates",
    [
        pytest.param("ACM LIR", 2, id="two-terms"),
        pytest.param("ACM acm LIR", 2, id="duplicate-term-gated-once"),
    ],
)
def test_every_term_is_scored_and_gated(fuzzy_term, gates):
    """Multi-term queries sample each term and require all terms to match."""
    candidates = select(AiSearchIndex.entity_id, AiSearchIndex.entity_title).distinct()
    stmt = FuzzyRetriever(fuzzy_term, cursor=None).apply(candidates)

    sql = str(stmt.compile(dialect=postgresql.dialect()))

    assert "WITH fuzzy_entities AS MATERIALIZED" in sql
    # One limit per sample, plus the starting-term selection and highlight lookup.
    assert sql.count("LIMIT %(param_") == gates + 2
    assert sql.count("EXISTS (SELECT") == gates
    # One filter per sample and per entity check, plus the starting term's filter.
    assert sql.count("<%") == 2 * gates + 1
    # The score appears in both SELECT and HAVING.
    assert sql.count("max(word_similarity(") == 2 * gates
    assert sql.count("HAVING") == 1
    assert "OVER (" not in sql
    assert "LATERAL" in sql

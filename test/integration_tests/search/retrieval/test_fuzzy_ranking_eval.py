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

"""Evaluation dataset for the fuzzy (trigram) retriever.

A small corpus shaped like real subscriptions (customer abbreviation, product, resource in the
description; product name and nested block values in other fields) and queries with the subscription
that should rank first. Each case is a regression guard; the aggregate hit@1 and MRR give a baseline
to compare ranking changes against instead of eyeballing single examples.

Only the trigram side is evaluated: it is deterministic, and the hybrid retriever falls back to it
when no embedding is available. Add real queries that misbehave in production as new cases.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.query.builder import build_candidate_query
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever

# entity key -> {path: value}
CORPUS: dict[str, dict[str, str]] = {
    "acm_lir": {
        "subscription.description": "ACM prefix LIR 192.0.2.0/24",
        "subscription.product.name": "IP Prefix",
        "subscription.ip_prefix.prefix": "192.0.2.0/24",
    },
    "acm_pa": {
        "subscription.description": "ACM prefix PA 198.51.100.0/24",
        "subscription.product.name": "IP Prefix",
        "subscription.ip_prefix.prefix": "198.51.100.0/24",
    },
    "bxt_lir": {
        "subscription.description": "BXT prefix LIR 203.0.113.0/24",
        "subscription.product.name": "IP Prefix",
        "subscription.ip_prefix.prefix": "203.0.113.0/24",
    },
    "zeo_lir": {
        "subscription.description": "ZEO prefix LIR 2001:db8:1::/48",
        "subscription.product.name": "IP Prefix",
        "subscription.ip_prefix.prefix": "2001:db8:1::/48",
    },
    "acm_l2vpn": {
        "subscription.description": "ACM L2VPN Hillcrest - Meadowbrook",
        "subscription.product.name": "L2VPN",
    },
    "acm_ip": {
        "subscription.description": "ACM IP BGP Riverton Hillcrest",
        "subscription.product.name": "InternetPlus",
    },
    "bxt_ip": {
        "subscription.description": "BXT IP static Harbour Park",
        "subscription.product.name": "InternetPlus",
    },
    "acm_lightpath": {
        "subscription.description": "ACM LightPath Riverton - Lakeside",
        "subscription.product.name": "LightPath",
    },
    "core_port": {
        "subscription.description": "Core port node01-rtr-01 et-0/0/1",
        "subscription.product.name": "Service Port",
        "subscription.port.node.name": "node01-rtr-01",
    },
}


@dataclass(frozen=True)
class EvalCase:
    query: str
    expected: str  # the CORPUS key that should rank first


EVAL_CASES = [
    # The issue: two terms that are both present but not adjacent
    EvalCase("ACM LIR", "acm_lir"),
    EvalCase("LIR ACM", "acm_lir"),
    EvalCase("acm lir", "acm_lir"),
    EvalCase("ACM prefix LIR", "acm_lir"),
    EvalCase("BXT LIR", "bxt_lir"),
    EvalCase("ZEO LIR", "zeo_lir"),
    EvalCase("ACM PA", "acm_pa"),
    # Typos
    EvalCase("ACM LIIR", "acm_lir"),
    EvalCase("Lightpth Riverton", "acm_lightpath"),
    # Contiguous phrases and single identifiers
    EvalCase("ACM L2VPN", "acm_l2vpn"),
    EvalCase("192.0.2.0/24", "acm_lir"),
    EvalCase("node01-rtr-01", "core_port"),
    # Terms spread over the description
    EvalCase("ACM LightPath Lakeside", "acm_lightpath"),
    EvalCase("Riverton Lakeside lightpath", "acm_lightpath"),
    EvalCase("BXT IP Harbour Park", "bxt_ip"),
    # Terms spread over different fields of the same subscription
    EvalCase("BXT InternetPlus", "bxt_ip"),
    EvalCase("ACM InternetPlus", "acm_ip"),
]


@pytest.fixture
def corpus_ids() -> dict[str, UUID]:
    ids = {key: uuid4() for key in CORPUS}
    db.session.add_all(
        AiSearchIndex(
            entity_type=EntityType.SUBSCRIPTION,
            entity_id=ids[key],
            entity_title=key,
            path=Ltree(path),
            value=value,
            value_type=FieldType.STRING,
            content_hash=uuid4().hex,
        )
        for key, fields in CORPUS.items()
        for path, value in fields.items()
    )
    db.session.commit()
    return ids


def _fuzzy_rows(query_text: str, limit: int) -> list:
    """Run the fuzzy retriever the way the engine does: its session settings first, then the statement."""
    retriever = FuzzyRetriever(query_text, cursor=None)
    for setting in retriever.session_settings:
        db.session.execute(text(setting.statement))
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query_text, limit=limit)
    return db.session.execute(retriever.apply(build_candidate_query(query))).mappings().all()


def _ranking(query_text: str, ids: dict[str, UUID]) -> list[str]:
    """The CORPUS keys in the order the fuzzy retriever ranks them."""
    key_by_id = {entity_id: key for key, entity_id in ids.items()}
    return [key_by_id[row.entity_id] for row in _fuzzy_rows(query_text, limit=len(ids))]


@pytest.mark.parametrize(
    "query_text,expected",
    [
        pytest.param("LIR", {"acm_lir", "bxt_lir", "zeo_lir"}, id="single-term"),
        # ACM alone gives every ACM subscription 0.5; LIR must also pass the gate somewhere ("Lakeside" is 0.5,
        # "L2VPN" is not) and the partial match then lifts the mean over the threshold
        pytest.param("ACM LIR", {"acm_lir", "acm_lightpath"}, id="one-exact-term-is-not-enough"),
        pytest.param("Riverton with frobnicator", set(), id="one-of-three-terms-matching-is-not-enough"),
        pytest.param("with", set(), id="term-absent-from-corpus"),
        pytest.param("xyzzy plugh", set(), id="no-term-matches"),
    ],
)
def test_entities_matching_too_few_terms_are_not_hits(corpus_ids, query_text, expected):
    """A field passes the gate on any term, but the entity is only kept when its mean over the terms is high."""
    assert set(_ranking(query_text, corpus_ids)) == expected


@pytest.mark.parametrize(
    "query_text,value,value_type,matches",
    [
        pytest.param("LIR", "LIR", FieldType.STRING, True, id="single-word"),
        pytest.param("LIR lir", "LIR", FieldType.STRING, True, id="duplicate-term"),
        pytest.param("LIR -", "LIR", FieldType.STRING, True, id="punctuation-dropped"),
        pytest.param(
            "123e4567-e89b-12d3-a456-426614174000",
            "123e4567-e89b-12d3-a456-426614174000",
            FieldType.UUID,
            True,
            id="uuid",
        ),
        pytest.param("12345", "12345", FieldType.INTEGER, False, id="non-searchable-field"),
        pytest.param("LIR", "LIP", FieldType.STRING, False, id="passes-gate-but-below-min-score"),
        pytest.param("xyzzy", "LIR", FieldType.STRING, False, id="no-match"),
        pytest.param("- / *", "LIR", FieldType.STRING, False, id="punctuation-only"),
    ],
)
def test_single_term_scores_and_highlights(query_text: str, value: str, value_type: FieldType, matches: bool) -> None:
    """Multiple matching fields yield one entity with its best score and shallowest highlight."""
    entity_id = uuid4()
    db.session.add_all(
        AiSearchIndex(
            entity_type=EntityType.SUBSCRIPTION,
            entity_id=entity_id,
            entity_title="single term",
            path=Ltree(path),
            value=field_value,
            value_type=field_type,
            content_hash=uuid4().hex,
        )
        for path, field_value, field_type in [
            ("subscription.description", value, value_type),
            ("subscription.block.description", value, value_type),
            ("subscription.status", "active", FieldType.STRING),
        ]
    )
    db.session.commit()

    rows = _fuzzy_rows(query_text, limit=10)

    assert [(row.entity_id, float(row.score), row.highlight_text, row.highlight_path) for row in rows] == (
        [(entity_id, 1.0, value, "subscription.description")] if matches else []
    )


@pytest.mark.parametrize(
    "fields,expected",
    [
        pytest.param([("subscription.description", "ACM LIP")], [0.75], id="partial-match-in-the-same-field"),
        pytest.param(
            [("subscription.customer", "ACM"), ("subscription.description", "LIP")],
            [0.75],
            id="partial-match-in-another-field",
        ),
        pytest.param([("subscription.customer", "ACM"), ("subscription.description", "LOL")], [], id="no-match"),
    ],
)
def test_every_term_must_pass_the_gate(fields, expected):
    """ACM matches exactly; LIR only counts, in whichever field, when its best match passes the gate (0.5 for LIP).

    An entity where LIR matches nothing is dropped even though ACM alone would give it 0.5.
    """
    entity_id = uuid4()
    db.session.add_all(
        AiSearchIndex(
            entity_type=EntityType.SUBSCRIPTION,
            entity_id=entity_id,
            entity_title="split",
            path=Ltree(path),
            value=value,
            value_type=FieldType.STRING,
            content_hash=uuid4().hex,
        )
        for path, value in fields
    )
    db.session.commit()

    rows = _fuzzy_rows("ACM LIR", limit=10)

    assert [(row.entity_id, float(row.score)) for row in rows] == [(entity_id, score) for score in expected]


def _reciprocal_rank(ranking: list[str], expected: str) -> float:
    return 1 / (ranking.index(expected) + 1) if expected in ranking else 0.0


@pytest.mark.parametrize("case", EVAL_CASES, ids=[case.query for case in EVAL_CASES])
def test_expected_subscription_ranks_first(corpus_ids, case):
    ranking = _ranking(case.query, corpus_ids)

    assert ranking[:1] == [case.expected], f"{case.query!r} ranked {ranking}"


def test_aggregate_ranking_quality(corpus_ids):
    """hit@1 and MRR over the whole dataset; raise the bar when ranking improves, never lower it."""
    rankings = [(_ranking(case.query, corpus_ids), case.expected) for case in EVAL_CASES]

    hit_at_1 = sum(ranking[:1] == [expected] for ranking, expected in rankings) / len(rankings)
    mrr = sum(_reciprocal_rank(ranking, expected) for ranking, expected in rankings) / len(rankings)

    assert (hit_at_1, mrr) == (1.0, 1.0)

# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

"""The search benchmark: accuracy per category and plan metrics of the fuzzy retriever, against committed baselines.

Both baselines are markdown under ``baseline/`` per Postgres major version, so a change shows as a readable diff.
Update them with ``pytest test/benchmarks/search --inline-snapshot=fix``; see the README.
"""

from pathlib import Path

import pytest
from inline_snapshot import external_file

from orchestrator.core.search.core.types import RetrieverType
from test.benchmarks.search.corpus import build_corpus
from test.benchmarks.search.perturb import Category, generate_queries
from test.benchmarks.search.profiles.generic import GenericProfile
from test.benchmarks.search.queries import load_handwritten
from test.benchmarks.search.runner import (
    accuracy_by_category,
    load_corpus,
    plan_scenarios,
    render_accuracy,
    run_queries,
    seq_scans_index_table,
    uses_trigram_index,
)
from test.integration_tests.search.performance._plans import postgres_major, render_plan_metrics

pytestmark = pytest.mark.search

SEED = 2000
CORPUS_SIZE = 3000
GENERATED_PER_CATEGORY = 20
RETRIEVER = RetrieverType.FUZZY
BASELINE = Path(__file__).parent / "baseline"


@pytest.fixture(scope="module")
def corpus():
    return build_corpus(GenericProfile(), SEED, CORPUS_SIZE)


@pytest.fixture
def loaded(corpus):
    return load_corpus(corpus)


@pytest.fixture
def queries(corpus):
    return [*load_handwritten(corpus), *generate_queries(corpus, GENERATED_PER_CATEGORY, SEED)]


@pytest.fixture
async def ran(loaded, corpus, queries, async_session):
    return await run_queries(async_session, corpus, queries, RETRIEVER)


def _assert_matches_baseline(name, page):
    assert page == external_file(BASELINE / f"{name}.pg{postgres_major()}.md", format=".txt")


def test_every_category_has_queries(queries):
    assert {query.category for query in queries} == set(Category)


def test_corpus_is_indexed_through_the_real_indexer(loaded, corpus):
    assert loaded > len(corpus.entities)


def test_accuracy_is_unchanged(ran, corpus):
    results, _ = ran
    page = render_accuracy(
        f"Search accuracy on Postgres {postgres_major()}",
        f"The {RETRIEVER.value} retriever on the `{corpus.profile}` profile: seed {corpus.seed}, {len(corpus.entities)} "
        "entities, hand-written and generated queries.",
        {RETRIEVER: accuracy_by_category(results)},
    )
    _assert_matches_baseline("accuracy", page)


def test_every_query_uses_the_trigram_index(ran):
    _, plans = ran
    assert [i for i, plan in enumerate(plans) if seq_scans_index_table(plan) or not uses_trigram_index(plan)] == []


def test_plan_metrics_are_unchanged(ran, corpus, queries):
    _, plans = ran
    page = render_plan_metrics(
        "Search benchmark plan metrics",
        f"The {RETRIEVER.value} retriever, one row per query, on {len(corpus.entities)} entities of the "
        f"`{corpus.profile}` profile (seed {corpus.seed}).",
        plan_scenarios(queries, plans),
    )
    _assert_matches_baseline("plans", page)

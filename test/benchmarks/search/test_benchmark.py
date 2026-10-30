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

"""The search benchmark: accuracy per category of the fuzzy retriever against a committed baseline.

The baseline is ``baseline/accuracy.md``, so a change shows as a readable diff. Update it with
``pytest test/benchmarks/search --inline-snapshot=fix``; see the README.
"""

from pathlib import Path

import pytest
from inline_snapshot import external_file

from orchestrator.core.search.core.types import RetrieverType
from test.benchmarks.search.corpus import build_corpus
from test.benchmarks.search.perturb import Category, generate_queries
from test.benchmarks.search.profiles.generic import GenericProfile
from test.benchmarks.search.queries import load_handwritten
from test.benchmarks.search.rankings import render_rankings
from test.benchmarks.search.runner import (
    accuracy_by_category,
    load_corpus,
    render_accuracy,
    run_queries,
    seq_scans_index_table,
    uses_trigram_index,
)

pytestmark = pytest.mark.search

SEED = 2000
CORPUS_SIZE = 3000
GENERATED_PER_CATEGORY = 20
RETRIEVER = RetrieverType.FUZZY
BASELINE = Path(__file__).parent / "baseline" / "accuracy.md"
# Not committed: the top results of every query of this run, to see why a metric moved.
REPORT = Path(__file__).parent / "report" / "rankings.md"


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
async def query_results(loaded, corpus, queries, async_session):
    return await run_queries(async_session, corpus, queries, RETRIEVER)


def _description(corpus):
    return f"The {RETRIEVER.value} retriever on the `{corpus.profile}` profile: seed {corpus.seed}, {len(corpus.entities)} entities."


def test_every_category_has_queries(queries):
    assert {query.category for query in queries} == set(Category)


def test_corpus_is_indexed_through_the_real_indexer(loaded, corpus):
    assert loaded > len(corpus.entities)


def test_accuracy_is_unchanged(query_results, corpus):
    results, _ = query_results
    page = render_accuracy("Search accuracy", _description(corpus), {RETRIEVER: accuracy_by_category(results)})
    assert page == external_file(BASELINE, format=".txt")


def test_rankings_are_written(query_results, corpus):
    results, _ = query_results
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(render_rankings("Search rankings", _description(corpus), results))


def test_every_query_uses_the_trigram_index(query_results, queries):
    _, plans = query_results
    offending = [
        q.text for q, plan in zip(queries, plans) if seq_scans_index_table(plan) or not uses_trigram_index(plan)
    ]
    assert offending == []

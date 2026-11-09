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

from contextlib import closing
from pathlib import Path

import pytest
from inline_snapshot import external_file
from sqlalchemy import text
from sqlalchemy.orm import close_all_sessions, scoped_session, sessionmaker

from orchestrator.core.db import db
from orchestrator.core.db.database import SESSION_ARGUMENTS
from orchestrator.core.search.core.types import RetrieverType
from test.benchmarks.search.corpus import build_corpus
from test.benchmarks.search.perturb import Category, generate_queries
from test.benchmarks.search.profiles.network_services import NetworkServicesProfile
from test.benchmarks.search.queries import load_handwritten_queries
from test.benchmarks.search.rankings import render_rankings
from test.benchmarks.search.runner import (
    accuracy_by_category,
    apply_benchmark_settings,
    load_corpus,
    render_accuracy,
    run_queries,
    seq_scans_index_table,
    settle_index,
    uses_trigram_index,
)
from test.benchmarks.search.settings import BASELINE, CORPUS_SIZE, GENERATED_PER_CATEGORY, SEED

pytestmark = pytest.mark.search

RETRIEVER = RetrieverType.FUZZY
ACCURACY = BASELINE / "accuracy.md"
# Not committed: the top results of every query of this run, to see why a metric moved.
REPORT = Path(__file__).parent / "report" / "rankings.md"


@pytest.fixture(scope="module")
def corpus():
    return build_corpus(NetworkServicesProfile(), SEED, CORPUS_SIZE)


@pytest.fixture(scope="module")
def loaded(corpus, database):
    """`corpus`, indexed once for the module and committed, as indexing it takes about a minute.

    The per-test transaction of `db_session` would roll the index back after every test. The module's tests only read
    it, and it is emptied again after them.
    """
    test_database = db.wrapped_database
    with closing(test_database.engine.connect()) as connection:
        # Bound to this connection as `db_session` binds the test connection, so the indexer joins its transaction.
        test_database.session_factory = sessionmaker(bind=connection, **SESSION_ARGUMENTS)
        test_database.scoped_session = scoped_session(test_database.session_factory, test_database._scopefunc)
        with connection.begin():
            # A vacuum or analyze at some moment during the tests would change their plans, so only `settle_index`
            # does them. Disabled in the load's own transaction, so the rows are never committed with autovacuum on.
            connection.execute(text("ALTER TABLE ai_search_index SET (autovacuum_enabled = false)"))
            written = load_corpus(corpus)
        close_all_sessions()
    with test_database.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        settle_index(connection)
    yield written
    # TRUNCATE fires no row triggers, so the paths the trigger derived from the index are emptied too.
    with test_database.engine.begin() as connection:
        connection.execute(text("TRUNCATE ai_search_index, ai_search_paths"))
        connection.execute(text("ALTER TABLE ai_search_index RESET (autovacuum_enabled)"))


@pytest.fixture
def queries(corpus):
    return [*load_handwritten_queries(corpus), *generate_queries(corpus, GENERATED_PER_CATEGORY, SEED)]


@pytest.fixture
async def query_results(loaded, corpus, queries, async_session):
    apply_benchmark_settings()
    return await run_queries(async_session, corpus, queries, RETRIEVER)


def _description(corpus):
    anchors = len(corpus.entities) - CORPUS_SIZE
    return (
        f"The {RETRIEVER.value} retriever on the `{corpus.profile}` profile, over {len(corpus.entities)} entities: "
        f"{anchors} hand-written anchors and {CORPUS_SIZE} generated with random seed {corpus.seed}."
    )


def test_every_category_has_queries(queries):
    assert {query.category for query in queries} == set(Category)


def test_corpus_is_indexed_through_the_real_indexer(loaded, corpus):
    assert loaded > len(corpus.entities)


def test_accuracy_is_unchanged(query_results, corpus):
    results, _ = query_results
    page = render_accuracy("Search accuracy", _description(corpus), {RETRIEVER: accuracy_by_category(results)})
    assert page == external_file(ACCURACY, format=".txt")


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

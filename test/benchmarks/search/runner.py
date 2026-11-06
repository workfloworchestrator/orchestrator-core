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

"""Index a corpus through the real indexer, run labelled queries through the real search engine, and report.

Accuracy is scored per category against the labels. The plan of each query's statement is captured too, to check
that it uses the trigram index; see `test.integration_tests.search.performance._plans`.
"""

from collections.abc import Mapping, Sequence

from more_itertools import one
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.db import db
from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.indexing.indexer import Indexer
from orchestrator.core.search.query.engine import execute_search
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.query.results import SearchResult
from test.benchmarks.search.corpus import CORPUS_ENTITY_CONFIG, Corpus
from test.benchmarks.search.metrics import CategoryMetrics, Hit, QueryResult, metrics_per_category
from test.benchmarks.search.perturb import LabelledQuery
from test.integration_tests.search.performance._plans import (
    GIST_INDEX,
    PLAN_SETTINGS,
    TRIGRAM_INDEX,
    _table,
    capturing_plans,
    plan_nodes,
)

# Pinned to Postgres' own default, so that a change of the server default cannot change the results unseen. The `<%`
# operator in the fuzzy retriever compares word_similarity to it.
WORD_SIMILARITY_THRESHOLD = "0.6"

DEFAULT_STATISTICS_TARGET = 100
# ANALYZE's sample size per unit of statistics target.
ROWS_PER_STATISTICS_TARGET = 300

BENCHMARK_SETTINGS = {**PLAN_SETTINGS, "pg_trgm.word_similarity_threshold": WORD_SIMILARITY_THRESHOLD}


def load_corpus(corpus: Corpus) -> int:
    """Replace the search index by `corpus`, indexed by the real `Indexer`.

    Embeddings are off (``EMBEDDING_API_ENABLED``), so the rows carry none: only the text retrievers are measured.
    Once committed, `settle_index` readies the table for plan reading.

    Returns:
        The number of index rows written.
    """
    db.session.execute(text("TRUNCATE ai_search_index"))
    written = Indexer(CORPUS_ENTITY_CONFIG, dry_run=False, force_index=True).run(corpus.entities)  # type: ignore[arg-type]
    # Rebuilt, so the index sizes do not depend on insertion order; see `_plans.seed_index`.
    for index in (GIST_INDEX, TRIGRAM_INDEX):
        db.session.execute(text(f"REINDEX INDEX {index}"))
    return written


def settle_index(connection: Connection) -> None:
    """VACUUM and ANALYZE the committed index on an autocommit `connection`, so its plans are the same on every run.

    Left to autovacuum, the table would be vacuumed and analyzed at some point during the tests, and its plans would
    change with it. Done here, autovacuum finds nothing left to do, as no test commits a change to the table.
    """
    # ANALYZE samples 300 * default_statistics_target rows, and a random sample gives run-dependent cost estimates. The
    # target is raised until the sample covers the whole table, so that it is read whole, as `_plans.seed_index` does.
    rows = connection.execute(text("SELECT count(*) FROM ai_search_index")).scalar_one()
    target = max(DEFAULT_STATISTICS_TARGET, -(-rows // ROWS_PER_STATISTICS_TARGET))
    connection.execute(text("SELECT set_config('default_statistics_target', :target, false)"), {"target": str(target)})
    # VACUUM sets the visibility map, which the planner reads for index-only scans.
    connection.execute(text("VACUUM (ANALYZE) ai_search_index"))
    connection.execute(text("RESET default_statistics_target"))


def apply_benchmark_settings() -> None:
    """Set `BENCHMARK_SETTINGS` for the rest of the current transaction."""
    for name, value in BENCHMARK_SETTINGS.items():
        db.session.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})


def uses_trigram_index(plan: Mapping) -> bool:
    return any(node.get("Index Name") == TRIGRAM_INDEX for node in plan_nodes(plan))


def seq_scans_index_table(plan: Mapping) -> bool:
    return any(
        node["Node Type"] == "Seq Scan" and node.get("Relation Name") == "ai_search_index" for node in plan_nodes(plan)
    )


async def run_query(
    session: AsyncSession, corpus: Corpus, query: LabelledQuery, retriever: RetrieverType
) -> tuple[QueryResult, Mapping]:
    """Search for `query` with `retriever`, and the plan of the statement that did it."""
    keys = {str(entity.entity_id): entity.key for entity in corpus.entities}
    select = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query.text, retriever=retriever)
    with capturing_plans() as plans:
        response = await execute_search(select, session)
    hits = tuple(_hit(result, keys) for result in response.results)
    return QueryResult(query, tuple(hit.key for hit in hits), hits), one(plans)


def _hit(result: SearchResult, keys: Mapping[str, str]) -> Hit:
    """The entity behind a search result, with the indexed value that matched it. Fuzzy search has one match per entity."""
    path, text = (
        (result.matching_fields[0].path, result.matching_fields[0].text) if result.matching_fields else ("", "")
    )
    return Hit(keys[result.entity_id], result.entity_title, path, text, result.score)


async def run_queries(
    session: AsyncSession, corpus: Corpus, queries: Sequence[LabelledQuery], retriever: RetrieverType
) -> tuple[list[QueryResult], list[Mapping]]:
    """Every query in order, with its plan. Sequential: the plans share one connection."""
    ran = [await run_query(session, corpus, query, retriever) for query in queries]
    return [result for result, _ in ran], [plan for _, plan in ran]


def _format(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def render_accuracy(
    title: str, description: str, by_retriever: Mapping[RetrieverType, Mapping[str, CategoryMetrics]]
) -> str:
    """A markdown page of the metrics per retriever and category, with a legend."""
    header = ["retriever", "category", "queries", "MRR", "Success@1", "Recall@10", "false positives"]
    rows = [
        [
            retriever.value,
            category,
            str(m.queries),
            *map(_format, (m.mrr, m.success_at_1, m.recall_at_10, m.false_positive_rate)),
        ]
        for retriever, categories in by_retriever.items()
        for category, m in categories.items()
    ]
    return f"""# {title}

{description}

Generated by the search benchmark. Update with `pytest test/benchmarks/search --inline-snapshot=fix`.

{_table(header, rows, text_columns=2)}

## Legend

A query is one search text the benchmark types into search, like a user would, for which we know in advance which
entities are the right answers. Queries are grouped into categories by how they are written: `exact` is a
description as stored, `typo` has a typing mistake, `negative` should find nothing, and so on. Some queries are
written by hand (`queries/network_services.yaml`); the rest are made by taking up to 20 entities and turning their
values into a query of each category.

Each query gets its own score from 0 to 1. A row shows the mean over the queries of its category: not the best or the
worst query, but how the category does on the whole. `report/rankings.md` has the results of each query.

- `queries`: how many queries the category has. A category with few queries moves a lot when one of them changes.
- `MRR` (Mean Reciprocal Rank): per query, 1 divided by the rank of the first right answer: 1 at rank 1, 0.5 at rank
  2, 0.33 at rank 3, 0 when it is not returned. The row is the mean of those.
- `Success@1`: the share of queries with a right answer on top. Stricter than MRR: rank 2 counts as a miss.
- `Recall@10`: per query, the share of its right answers in the top 10. A query with more than 10 right answers needs
  only 10 of them. Is it found at all, even if not on top?
- `false positives`: the share of `negative` queries, which have no right answer in the corpus, that returned
  anything. Lower is better. The only check on the `<%` threshold. The other categories have no such column: a wrong
  result above the right one already lowers their MRR and Success@1.

How to read a row:

- High Recall@10 with low Success@1: search finds the answer but ranks it too low.
- MRR equal to Success@1: no right answer ranks 2nd or lower. Each query has one on top or doesn't return one, so
  the misses are matching problems, not ranking problems.
- MRR well above Success@1: right answers often rank just below the top, so the ranking is off, not the matching.
- Success@1 of 1 with Recall@10 below 1: every query has a right answer on top, but not all of its right answers
  made the top 10.
- Low scores on all three: search does not find the answer at all, the matching is off.
- With 4 `negative` queries, false positives of 0.250 means one of them returned results.
"""


def accuracy_by_category(results: Sequence[QueryResult]) -> Mapping[str, CategoryMetrics]:
    return {category.value: metrics for category, metrics in metrics_per_category(results).items()}

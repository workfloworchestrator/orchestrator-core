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
from sqlalchemy import text
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
    """Replace the search index by `corpus`, indexed by the real `Indexer`, and settle the database for plan reading.

    Embeddings are off (``EMBEDDING_API_ENABLED``), so the rows carry none: only the text retrievers are measured.

    Returns:
        The number of index rows written.
    """
    db.session.execute(text("TRUNCATE ai_search_index"))
    written = Indexer(CORPUS_ENTITY_CONFIG, dry_run=False, force_index=True).run(corpus.entities)  # type: ignore[arg-type]
    # Rebuilt, so the index sizes do not depend on insertion order; see `_plans.seed_index`. VACUUM cannot run in the
    # test transaction, but a freshly truncated table has no dead rows: ANALYZE is what settles the statistics.
    for index in (GIST_INDEX, TRIGRAM_INDEX):
        db.session.execute(text(f"REINDEX INDEX {index}"))
    # ANALYZE samples 300 * default_statistics_target rows, and a random sample gives run-dependent cost estimates. The
    # target is raised until the sample covers the whole table, so that it is read whole, as `_plans.seed_index` does.
    rows = db.session.execute(text("SELECT count(*) FROM ai_search_index")).scalar_one()
    target = max(DEFAULT_STATISTICS_TARGET, -(-rows // ROWS_PER_STATISTICS_TARGET))
    db.session.execute(text("SELECT set_config('default_statistics_target', :target, true)"), {"target": str(target)})
    db.session.execute(text("ANALYZE ai_search_index"))
    for name, value in BENCHMARK_SETTINGS.items():
        db.session.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})
    return written


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
    return Hit(keys[result.entity_id], result.entity_title, path, text)


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
    header = "| retriever | category | queries | MRR | Success@1 | Recall@10 | false positives |"
    rows = [
        f"| {retriever.value} | {category} | {m.queries} | {_format(m.mrr)} | {_format(m.success_at_1)} "
        f"| {_format(m.recall_at_10)} | {_format(m.false_positive_rate)} |"
        for retriever, categories in by_retriever.items()
        for category, m in categories.items()
    ]
    separator = "|" + "|".join(["---", "---", "---:", "---:", "---:", "---:", "---:"]) + "|"
    return f"""# {title}

{description}

Generated by the search benchmark. Update with `pytest test/benchmarks/search --inline-snapshot=fix`.

{header}
{separator}
{chr(10).join(rows)}

## Legend

All scores run from 0 to 1, averaged over the queries of a category.

- `MRR`: how high the first right answer ranks. 1 at rank 1, 0.5 at rank 2, 0.33 at rank 3, 0 when not found.
- `Success@1`: the share of queries with a right answer on top. Stricter than MRR: rank 2 counts as a miss.
- `Recall@10`: the share of right answers in the top 10, capped at 10. Is it found at all, even if not on top?
- `false positives`: the share of `negative` queries that returned anything; lower is better. The only check on the
  `<%` threshold.

High Recall@10 with low Success@1 means search finds the answer but ranks it too low.
"""


def accuracy_by_category(results: Sequence[QueryResult]) -> Mapping[str, CategoryMetrics]:
    return {category.value: metrics for category, metrics in metrics_per_category(results).items()}

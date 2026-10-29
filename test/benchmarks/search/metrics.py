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

"""Accuracy metrics of ranked results against labelled queries, per category and retriever. Pure functions."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import groupby
from statistics import mean

from test.benchmarks.search.perturb import Category, LabelledQuery

RECALL_CUTOFF = 10


@dataclass(frozen=True)
class Hit:
    """A returned entity: its key, its title and the indexed value the score came from."""

    key: str
    title: str = ""
    matched_path: str = ""
    matched_text: str = ""


@dataclass(frozen=True)
class QueryResult:
    """A query and the entity keys search returned for it, best first.

    `hits` are the same entities as `ranked`, with what the ranking report shows of each. Metrics only need `ranked`.
    """

    query: LabelledQuery
    ranked: tuple[str, ...]
    hits: tuple[Hit, ...] = ()


@dataclass(frozen=True)
class CategoryMetrics:
    """Metrics of one category. `false_positive_rate` is only defined for `negative` queries, the others have none."""

    queries: int
    mrr: float | None
    success_at_1: float | None
    recall_at_10: float | None
    false_positive_rate: float | None


def reciprocal_rank(ranked: Sequence[str], expected: Iterable[str]) -> float:
    """1 / the rank of the first expected entity, 0 if none was returned."""
    wanted = set(expected)
    return next((1 / rank for rank, key in enumerate(ranked, start=1) if key in wanted), 0.0)


def success_at_1(ranked: Sequence[str], expected: Iterable[str]) -> float:
    return float(bool(ranked) and ranked[0] in set(expected))


def recall_at(ranked: Sequence[str], expected: Sequence[str], cutoff: int = RECALL_CUTOFF) -> float:
    """The share of expected entities among the first `cutoff` results.

    A query made from a shared fact (a city, a customer) expects hundreds of entities, of which no more than `cutoff`
    fit. The share is of what could fit: finding `cutoff` of them is full recall.
    """
    return len(set(ranked[:cutoff]) & set(expected)) / min(len(expected), cutoff)


def category_metrics(results: Sequence[QueryResult]) -> CategoryMetrics:
    """Metrics of results of one category. Negative queries only count towards the false-positive rate.

    Raises:
        ValueError: When `results` mixes negative and positive queries, or is empty.
    """
    if not results:
        raise ValueError("No results to score")
    negative = [not result.query.expected for result in results]
    if any(negative) and not all(negative):
        raise ValueError("A category holds either queries with expected entities or without, not both")
    if all(negative):
        return CategoryMetrics(len(results), None, None, None, mean(float(bool(r.ranked)) for r in results))
    return CategoryMetrics(
        queries=len(results),
        mrr=mean(reciprocal_rank(r.ranked, r.query.expected) for r in results),
        success_at_1=mean(success_at_1(r.ranked, r.query.expected) for r in results),
        recall_at_10=mean(recall_at(r.ranked, r.query.expected) for r in results),
        false_positive_rate=None,
    )


def metrics_per_category(results: Iterable[QueryResult]) -> Mapping[Category, CategoryMetrics]:
    """Metrics per category, in the order of `Category`."""
    ordered = sorted(results, key=lambda r: list(Category).index(r.query.category))
    return {
        category: category_metrics(list(group)) for category, group in groupby(ordered, key=lambda r: r.query.category)
    }

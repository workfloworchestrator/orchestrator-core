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

import pytest

from test.benchmarks.search.metrics import (
    QueryResult,
    category_metrics,
    metrics_per_category,
    recall_at,
    reciprocal_rank,
    success_at_1,
)
from test.benchmarks.search.perturb import Category, LabelledQuery


def _result(ranked, expected, category=Category.TYPO):
    return QueryResult(LabelledQuery("q", category, tuple(expected)), tuple(ranked))


@pytest.mark.parametrize(
    "ranked,expected,rr",
    [
        (["a", "b"], ["a"], 1.0),
        (["b", "a"], ["a"], 0.5),
        (["b", "c"], ["a"], 0.0),
        ([], ["a"], 0.0),
        (["b", "a"], ["a", "b"], 1.0),
    ],
)
def test_reciprocal_rank(ranked, expected, rr):
    assert reciprocal_rank(ranked, expected) == rr


@pytest.mark.parametrize(
    "ranked,expected,hit",
    [(["a"], ["a"], 1.0), (["b", "a"], ["a"], 0.0), ([], ["a"], 0.0)],
)
def test_success_at_1(ranked, expected, hit):
    assert success_at_1(ranked, expected) == hit


@pytest.mark.parametrize(
    "ranked,expected,cutoff,recall",
    [
        (["a", "b"], ["a", "b"], 10, 1.0),
        (["a"], ["a", "b"], 10, 0.5),
        (["a", "b", "c"], ["c"], 2, 0.0),
        # More expected than fit: finding `cutoff` of them is full recall.
        (["a", "b"], ["a", "b", "c", "d"], 2, 1.0),
    ],
)
def test_recall_at(ranked, expected, cutoff, recall):
    assert recall_at(ranked, expected, cutoff) == recall


def test_category_metrics_means_over_queries():
    metrics = category_metrics([_result(["a"], ["a"]), _result(["b", "a"], ["a"])])

    assert (metrics.queries, metrics.mrr, metrics.success_at_1, metrics.recall_at_10) == (2, 0.75, 0.5, 1.0)
    assert metrics.false_positive_rate is None


def test_negative_queries_report_only_false_positives():
    metrics = category_metrics([_result([], [], Category.NEGATIVE), _result(["x"], [], Category.NEGATIVE)])

    assert (metrics.mrr, metrics.recall_at_10, metrics.false_positive_rate) == (None, None, 0.5)


@pytest.mark.parametrize(
    "results,message",
    [([], "No results"), ([_result([], []), _result(["a"], ["a"])], "either")],
)
def test_category_metrics_rejects_bad_input(results, message):
    with pytest.raises(ValueError, match=message):
        category_metrics(results)


def test_metrics_per_category_groups_and_orders_by_category():
    results = [_result(["a"], ["a"], Category.TYPO), _result(["a"], ["a"], Category.EXACT)]

    assert list(metrics_per_category(results)) == [Category.EXACT, Category.TYPO]

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

import re

import pytest

from test.benchmarks.search.metrics import Hit, QueryResult
from test.benchmarks.search.perturb import Category, LabelledQuery
from test.benchmarks.search.rankings import RANKING_CUTOFF, SHOWN_EXPECTED, passed, render_rankings


def _result(text, ranked, expected=(), category=Category.IDENTIFIER, hits=()):
    return QueryResult(LabelledQuery(text, category, tuple(expected)), tuple(ranked), tuple(hits))


def _page(results):
    return render_rankings("Title", "Description", results)


def _row(page, prefix):
    return next(line for line in page.splitlines() if line.startswith(prefix))


def _summary_links(page):
    """The query text and section anchor of every summary row, in page order."""
    summary = page.split("## Summary")[1].split("## Queries")[0]
    return re.findall(r"\[`([^`]+)`\]\(#(q\d+)\)", summary)


def _section(page, anchor):
    return page.split(f'<a id="{anchor}"></a>')[1].split("<a id=")[0]


@pytest.mark.parametrize(
    "ranked,expected,category,result",
    [
        pytest.param(["a", "b"], ["a"], Category.IDENTIFIER, True, id="right answer on top"),
        pytest.param(["b", "a"], ["a"], Category.IDENTIFIER, False, id="right answer second"),
        pytest.param(["b", "a"], ["a", "b"], Category.IDENTIFIER, True, id="two right answers"),
        pytest.param([], ["a"], Category.IDENTIFIER, False, id="nothing returned"),
        pytest.param([], [], Category.NEGATIVE, True, id="negative, nothing returned"),
        pytest.param(["a"], [], Category.NEGATIVE, False, id="negative, false positive"),
    ],
)
def test_passed(ranked, expected, category, result):
    assert passed(_result("q", ranked, expected, category)) is result


@pytest.mark.parametrize("returned", [1, 3, RANKING_CUTOFF + 5])
def test_at_most_the_cutoff_is_shown(returned):
    ranked = [f"gen-{i}" for i in range(returned)]

    rows = [line for line in _page([_result("q", ranked)]).splitlines() if line.startswith("| ") and " gen-" in line]

    assert len(rows) == min(returned, RANKING_CUTOFF)


def test_pipes_and_newlines_in_values_do_not_break_the_table():
    page = _page([_result("q", ["a"], hits=[Hit("a", "first|second\nthird", "p", "x")])])

    assert "| first\\|second third |" in _row(page, "| 1 |")


@pytest.mark.parametrize(
    "ranked,expected,verdict",
    [
        pytest.param(
            ["x", "a"],
            ["a", "b"],
            "Expects 2: a, b.  \nFirst right answer: rank 2. Right answers in top 10: 1 of 2.  \n"
            "Missing from top 10: b.\n",
            id="ranked low, one missing",
        ),
        pytest.param(
            ["k0"],
            [f"k{i}" for i in range(SHOWN_EXPECTED + 3)],
            f"Expects {SHOWN_EXPECTED + 3}: {', '.join(f'k{i}' for i in range(SHOWN_EXPECTED))}, … 3 more.  \n"
            "First right answer: rank 1. Right answers in top 10: 1 of 10.\n",
            id="more than fit, missing not listed",
        ),
    ],
)
def test_verdict(ranked, expected, verdict):
    assert verdict in _page([_result("q", ranked, expected)])


def test_summary_lists_misses_first_in_benchmark_order_and_links_to_sections():
    results = [
        _result("hit", ["a"], ["a"]),
        _result("low", ["x", "a"], ["a"]),
        _result("noise", ["x"], category=Category.NEGATIVE),
        _result("quiet", [], category=Category.NEGATIVE),
    ]

    page = _page(results)

    links = _summary_links(page)

    assert [text for text, _ in links] == ["low", "noise", "hit", "quiet"]
    assert all(f"`{text}`" in _section(page, anchor) for text, anchor in links)

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

from test.benchmarks.search.metrics import Hit, QueryResult
from test.benchmarks.search.perturb import Category, LabelledQuery
from test.benchmarks.search.rankings import RANKING_CUTOFF, render_rankings


def _result(text, ranked, expected=(), category=Category.IDENTIFIER, hits=()):
    return QueryResult(LabelledQuery(text, category, tuple(expected)), tuple(ranked), tuple(hits))


def _page(results):
    return render_rankings("Title", "Description", results)


def test_query_is_the_heading_above_its_ranked_results():
    page = _page([_result("ams001a-rt01", ["ams001a-rt01", "gen-1"], expected=["ams001a-rt01"])])

    assert "### identifier · query: `ams001a-rt01`\n" in page
    assert "| 1 | ams001a-rt01 |  |  |  | ✓ |" in page
    assert "| 2 | gen-1 |  |  |  |  |" in page


@pytest.mark.parametrize("returned", [1, 3, RANKING_CUTOFF + 5])
def test_at_most_the_cutoff_is_shown(returned):
    ranked = [f"gen-{i}" for i in range(returned)]

    rows = [line for line in _page([_result("q", ranked)]).splitlines() if line.startswith("| ") and "gen-" in line]

    assert len(rows) == min(returned, RANKING_CUTOFF)


def test_query_without_results_renders_an_empty_table():
    page = _page([_result("nothing", [], category=Category.NEGATIVE)])

    assert "### negative · query: `nothing`" in page
    assert "| # | entity | title | matched path | matched value | expected |" in page


def test_matched_title_path_and_value_are_shown():
    hit = Hit("ams001a-rt01", "NWR LP AMS001A", "subscription.vc.saps.0.port.port_name", "xe-1/2/4")

    page = _page([_result("q", ["ams001a-rt01"], hits=[hit])])

    assert "| 1 | ams001a-rt01 | NWR LP AMS001A | subscription.vc.saps.0.port.port_name | xe-1/2/4 |  |" in page


def test_pipes_and_newlines_in_values_do_not_break_the_table():
    hit = Hit("a", "first|second\nthird", "p", "x")

    row = next(line for line in _page([_result("q", ["a"], hits=[hit])]).splitlines() if line.startswith("| 1 |"))

    assert row == "| 1 | a | first\\|second third | p | x |  |"


def test_long_values_are_shortened():
    hit = Hit("a", "x" * 200)

    row = next(line for line in _page([_result("q", ["a"], hits=[hit])]).splitlines() if line.startswith("| 1 |"))

    assert ("x" * 79 + "…") in row
    assert ("x" * 80) not in row

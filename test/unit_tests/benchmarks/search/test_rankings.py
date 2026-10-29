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
from test.benchmarks.search.rankings import DRIFT, NEW_QUERY, RANKING_CUTOFF, read_rankings, render_rankings


def _result(text, ranked, expected=(), category=Category.IDENTIFIER):
    return QueryResult(LabelledQuery(text, category, tuple(expected)), tuple(ranked))


def _page(results, baseline=None):
    return render_rankings("Title", "Description", results, baseline)


def test_query_is_the_heading_above_its_ranked_results():
    page = _page([_result("ams001a-rt01", ["ams001a-rt01", "gen-1"], expected=["ams001a-rt01"])])

    assert "### identifier · query: `ams001a-rt01`\n" in page
    assert "| 1 | ams001a-rt01 |  |  |  | ✓ |  |" in page
    assert "| 2 | gen-1 |  |  |  |  |  |" in page


@pytest.mark.parametrize("returned", [1, 3, RANKING_CUTOFF + 5])
def test_at_most_the_cutoff_is_shown(returned):
    ranked = [f"gen-{i}" for i in range(returned)]

    rows = [line for line in _page([_result("q", ranked)]).splitlines() if line.startswith("| ") and "gen-" in line]

    assert len(rows) == min(returned, RANKING_CUTOFF)


def test_no_baseline_marks_nothing():
    page = _page([_result("q", ["a"])])

    assert "No baseline yet" in page
    assert DRIFT not in page
    assert NEW_QUERY not in page


def test_unchanged_ranking_is_not_marked():
    results = [_result("q", ["a", "b"])]
    baseline = {("identifier", "q"): ("a", "b")}

    page = _page(results, baseline)

    assert DRIFT not in page
    assert "0 drifted from the baseline" in page


def test_changed_ranking_is_marked_in_the_heading():
    results = [_result("q", ["b", "a"])]
    baseline = {("identifier", "q"): ("a", "b")}

    page = _page(results, baseline)

    assert "### identifier · query: `q` — ⚠ drift" in page
    assert "1 drifted from the baseline" in page


def test_moved_entity_shows_its_old_rank():
    results = [_result("q", ["b", "a"])]
    baseline = {("identifier", "q"): ("a", "b")}

    page = _page(results, baseline)

    assert "| 1 | b |  |  |  |  | was #2 |" in page
    assert "| 2 | a |  |  |  |  | was #1 |" in page


def test_entity_not_in_baseline_is_marked_new():
    results = [_result("q", ["a", "x"])]
    baseline = {("identifier", "q"): ("a",)}

    page = _page(results, baseline)

    assert "| 2 | x |  |  |  |  | new |" in page


def test_entity_dropped_from_the_top_is_listed():
    results = [_result("q", ["a"])]
    baseline = {("identifier", "q"): ("a", "b")}

    page = _page(results, baseline)

    assert "Dropped from the top 10: `b`" in page


def test_query_missing_from_baseline_is_new():
    results = [_result("q", ["a"])]

    page = _page(results, {("identifier", "other"): ("a",)})

    assert "### identifier · query: `q` — new query" in page
    assert "1 new" in page


def test_same_text_in_two_categories_is_two_queries():
    results = [_result("q", ["a"], category=Category.TYPO), _result("q", ["b"], category=Category.EXACT)]
    baseline = {("typo", "q"): ("a",), ("exact", "q"): ("a",)}

    page = _page(results, baseline)

    assert "### typo · query: `q`\n" in page
    assert "### exact · query: `q` — ⚠ drift" in page


def test_read_rankings_round_trips_a_rendered_page():
    results = [_result("q1", ["a", "b"]), _result("q2", ["c"], category=Category.TYPO)]

    assert read_rankings(_page(results)) == {("identifier", "q1"): ("a", "b"), ("typo", "q2"): ("c",)}


def test_read_rankings_ignores_text_outside_sections():
    assert read_rankings("# Title\n\n| 1 | a |  |  |\n") == {}


def test_render_then_compare_against_itself_has_no_drift():
    results = [_result("q", ["a", "b", "c"], expected=["a"])]
    baseline = read_rankings(_page(results))

    page = _page(results, baseline)

    assert DRIFT not in page
    assert NEW_QUERY not in page


def test_query_without_results_renders_an_empty_table():
    page = _page([_result("nothing", [], category=Category.NEGATIVE)])

    assert "### negative · query: `nothing`" in page
    assert "| # | entity | title | matched path | matched value | expected | vs baseline |" in page


def test_matched_title_path_and_value_are_shown():
    hit = Hit("ams001a-rt01", "NWR LP AMS001A", "subscription.vc.saps.0.port.port_name", "xe-1/2/4")
    result = QueryResult(LabelledQuery("q", Category.IDENTIFIER, ()), ("ams001a-rt01",), (hit,))

    page = _page([result])

    assert "| 1 | ams001a-rt01 | NWR LP AMS001A | subscription.vc.saps.0.port.port_name | xe-1/2/4 |  |  |" in page


def test_pipes_and_newlines_in_values_do_not_break_the_table():
    hit = Hit("a", "first|second\nthird", "p", "x")
    result = QueryResult(LabelledQuery("q", Category.IDENTIFIER, ()), ("a",), (hit,))

    row = next(line for line in _page([result]).splitlines() if line.startswith("| 1 |"))

    assert row == "| 1 | a | first\\|second third | p | x |  |  |"


def test_long_values_are_shortened():
    hit = Hit("a", "x" * 200)
    result = QueryResult(LabelledQuery("q", Category.IDENTIFIER, ()), ("a",), (hit,))

    row = next(line for line in _page([result]).splitlines() if line.startswith("| 1 |"))

    assert ("x" * 79 + "…") in row
    assert ("x" * 80) not in row

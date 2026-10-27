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

from test.benchmarks.search.perturb import Category, LabelledQuery
from test.benchmarks.search.runner import plan_scenarios

PLAN = {
    "Node Type": "Result",
    "Total Cost": 1.0,
    "Shared Hit Blocks": 1,
    "Shared Read Blocks": 0,
    "Actual Rows": 1,
    "Actual Loops": 1,
    "Function Calls": 0,
}


def _query(category):
    return LabelledQuery(text="q", category=category, expected=())


def test_plan_scenarios_are_numbered_within_their_category():
    queries = [_query(Category.TYPO), _query(Category.EXACT), _query(Category.TYPO), _query(Category.EXACT)]

    assert list(plan_scenarios(queries, [PLAN] * 4)) == ["typo-1", "exact-1", "typo-2", "exact-2"]


def test_adding_a_query_to_one_category_keeps_the_other_names():
    queries = [_query(Category.TYPO), _query(Category.EXACT)]
    extended = [*queries, _query(Category.TYPO)]

    before, after = plan_scenarios(queries, [PLAN] * 2), plan_scenarios(extended, [PLAN] * 3)
    assert set(before) <= set(after)
    assert set(after) - set(before) == {"typo-2"}

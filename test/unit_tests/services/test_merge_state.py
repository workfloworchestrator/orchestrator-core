# Copyright 2019-2026 SURF, GÉANT.
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
"""Checks `merge_state` against `StateMerger`, the deepmerge-based merger it replaced."""

from copy import deepcopy
from typing import Any

import pytest
from deepmerge.merger import Merger

from orchestrator.core.services.processes import merge_state

# Exact configuration `StateMerger` used before its removal.
StateMerger = Merger([(dict, ["merge"])], ["override"], ["override"])


MERGE_CASES = [
    pytest.param({}, {}, {}, id="both-empty"),
    pytest.param({"a": 1}, {}, {"a": 1}, id="empty-nxt-keeps-base"),
    pytest.param({}, {"a": 1}, {"a": 1}, id="empty-base-takes-nxt"),
    pytest.param({"a": 1}, {"b": 2}, {"a": 1, "b": 2}, id="disjoint-keys-union"),
    pytest.param({"a": 1}, {"a": 2}, {"a": 2}, id="scalar-scalar-nxt-wins"),
    pytest.param({"a": 1}, {"a": None}, {"a": None}, id="none-overrides-scalar"),
    pytest.param({"a": None}, {"a": 1}, {"a": 1}, id="scalar-overrides-none"),
    pytest.param({"a": [1, 2]}, {"a": [3]}, {"a": [3]}, id="list-list-nxt-replaces-whole-list"),
    pytest.param({"a": {"x": 1}}, {"a": [1]}, {"a": [1]}, id="dict-base-list-nxt-type-conflict"),
    pytest.param({"a": [1]}, {"a": {"x": 1}}, {"a": {"x": 1}}, id="list-base-dict-nxt-type-conflict"),
    pytest.param(
        {"a": {"x": 1, "y": 2}},
        {"a": {"y": 3, "z": 4}},
        {"a": {"x": 1, "y": 3, "z": 4}},
        id="nested-dict-shallow-merge",
    ),
    pytest.param(
        {"a": {"b": {"c": 1, "d": 2}}},
        {"a": {"b": {"d": 3, "e": 4}}},
        {"a": {"b": {"c": 1, "d": 3, "e": 4}}},
        id="nested-dict-deep-merge",
    ),
    pytest.param(
        {"a": {"b": 1}},
        {"a": {}},
        {"a": {"b": 1}},
        id="empty-nxt-dict-keeps-base-dict-contents",
    ),
    pytest.param(
        {"a": {}},
        {"a": {"b": 1}},
        {"a": {"b": 1}},
        id="empty-base-dict-takes-nxt-dict-contents",
    ),
    pytest.param(
        {"a": {"items": [{"id": 1, "name": "x"}, {"id": 2, "name": "y"}]}},
        {"a": {"items": [{"id": 1, "name": "z"}]}},
        {"a": {"items": [{"id": 1, "name": "z"}]}},
        id="list-of-objects-under-dict-replaced-wholesale-not-merged-per-item",
    ),
]


@pytest.mark.parametrize("base,nxt,expected", MERGE_CASES)
def test_merge_state_matches_state_merger(base: dict[str, Any], nxt: dict[str, Any], expected: dict[str, Any]) -> None:
    """Direct head-to-head: `merge_state` and `StateMerger.merge` must agree on every case."""
    old_result = StateMerger.merge(deepcopy(base), deepcopy(nxt))
    new_result = merge_state(deepcopy(base), deepcopy(nxt))
    assert new_result == old_result == expected


def test_state_merger_mutates_base_in_place() -> None:
    """Documents the old, surprising behaviour that callers used to `deepcopy(state)` to avoid."""
    base = {"a": {"x": 1}}
    nxt = {"a": {"y": 2}}

    result = StateMerger.merge(base, nxt)

    assert result is base
    assert base == {"a": {"x": 1, "y": 2}}


def test_merge_state_does_not_mutate_base_or_nxt() -> None:
    """The deliberate behavioural change: `merge_state` is pure, so callers no longer need `deepcopy`."""
    base = {"a": {"x": 1}}
    nxt = {"a": {"y": 2}}
    base_snapshot = deepcopy(base)
    nxt_snapshot = deepcopy(nxt)

    result = merge_state(base, nxt)

    assert result == {"a": {"x": 1, "y": 2}}
    assert result is not base
    assert base == base_snapshot
    assert nxt == nxt_snapshot

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

"""Unit tests for the beta parallel steps DSL, branching helpers and executor dispatch.

Every test here covers ``orchestrator.core.beta.parallel``: the branch step naming, the branch reconstruction, the
worst-branch status, the definition-time validation and the worker dispatch. The behaviour that stays in stable code (the
step tree walk and the group-name check) are tested in ``test/unit_tests/test_workflow.py``.
"""

from __future__ import annotations

import pytest

from orchestrator.core.beta.parallel import map_parallel, parallel
from orchestrator.core.beta.parallel.branching import _worst_status as worst_status
from orchestrator.core.beta.parallel.branching import branch_step_name, reconstruct_branch
from orchestrator.core.workflow import (
    AwaitingCallback,
    Failed,
    Success,
    Suspend,
    Waiting,
    begin,
    step,
)


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


@pytest.mark.parametrize(
    "construct",
    [
        pytest.param(
            lambda: parallel("Parallel", begin >> _step_a, begin >> _step_b, max_concurrency=0), id="parallel"
        ),
        pytest.param(lambda: map_parallel("Map", "items", begin >> _step_a, max_concurrency=-1), id="map-parallel"),
    ],
)
def test_parallel_step_rejects_non_positive_concurrency_at_definition(construct):
    with pytest.raises(ValueError, match="max_concurrency must be greater than 0"):
        construct()


@pytest.mark.parametrize(
    "results, expected_check",
    [
        ([Failed({"error": "boom"})], "isfailed"),
        ([Waiting({"w": 1})], "iswaiting"),
        ([Suspend({"s": 1})], "issuspend"),
        ([AwaitingCallback({"ac": 1})], "isawaitingcallback"),
        ([Success({"a": 1}), Success({"b": 2})], None),
        ([Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
        ([Suspend({"s": 1}), Failed({"error": "x"})], "isfailed"),
        ([AwaitingCallback({"ac": 1}), Failed({"error": "x"})], "isfailed"),
        ([Suspend({"s": 1}), Waiting({"w": 1})], "iswaiting"),
        ([AwaitingCallback({"ac": 1}), Waiting({"w": 1})], "iswaiting"),
        ([AwaitingCallback({"ac": 1}), Suspend({"s": 1})], "issuspend"),
        ([Success({"a": 1}), Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
        ([Success({"a": 1}), Suspend({"s": 1}), AwaitingCallback({"ac": 1})], "issuspend"),
    ],
    ids=[
        "single-failed",
        "single-waiting",
        "single-suspend",
        "single-awaiting-callback",
        "all-success",
        "waiting-and-failed",
        "suspend-and-failed",
        "awaiting-callback-and-failed",
        "suspend-and-waiting",
        "awaiting-callback-and-waiting",
        "awaiting-callback-and-suspend",
        "three-branches-failed-wins",
        "three-branches-suspend-wins",
    ],
)
def test_worst_status_priority(results: list, expected_check: str | None) -> None:
    worst = worst_status(results)
    if expected_check is None:
        assert worst is None
    else:
        assert worst is not None
        assert getattr(worst, expected_check)()


def test_callback_step_in_parallel_raises() -> None:
    from orchestrator.core.workflow import callback_step

    @step("CB Action")
    def _cb_action() -> dict:
        return {}

    @step("CB Validate")
    def _cb_validate() -> dict:
        return {}

    _test_callback = callback_step("Test callback", _cb_action, _cb_validate)

    @step("Branch A")
    def branch_a() -> dict:
        return {"a": 1}

    with pytest.raises(ValueError, match="callback"):
        # Tests both a StepList and Step
        parallel("Invalid parallel", begin >> branch_a, _test_callback)


# -- reconstruct_branch --


def test_reconstruct_branch_returns_step_list() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    branch = reconstruct_branch(par_step, 0)
    assert len(branch) > 0


def test_reconstruct_branch_returns_the_branch_at_the_index() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    assert par_step.branching is not None
    assert reconstruct_branch(par_step, 1) == par_step.branching.branches[1]


def test_reconstruct_branch_index_out_of_range_raises() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    with pytest.raises(IndexError):
        reconstruct_branch(par_step, 5)


def test_reconstruct_branch_of_a_step_that_does_not_branch_raises() -> None:
    with pytest.raises(ValueError, match="not a parallel step"):
        reconstruct_branch(_step_a, 0)


@pytest.mark.parametrize("branch_index", [0, 1, 7])
def test_reconstruct_branch_of_map_parallel_returns_the_template(branch_index: int) -> None:
    """Every item of a map_parallel runs the same template, whatever the branch index."""
    template = begin >> _step_a
    step_fn = map_parallel("Per item", "items", template)

    assert reconstruct_branch(step_fn, branch_index) == template


# -- branch step names --


@pytest.mark.parametrize(
    "branch_index, step_name, expected",
    [
        pytest.param(0, "Provision", "[Branch 0] Provision", id="first-branch"),
        pytest.param(12, "[x] y", "[Branch 12] [x] y", id="keeps-brackets-in-the-step-name"),
        pytest.param(1, "", "[Branch 1] ", id="empty-step-name"),
    ],
)
def test_branch_step_name_prefixes_the_branch_index(branch_index: int, step_name: str, expected: str) -> None:
    """A branch step row is named after its step, prefixed with the branch the step belongs to."""
    assert branch_step_name(branch_index, step_name) == expected

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

"""The step tree walk and the group-name lookup stay in stable code, so their tests live here.

``_find_step_by_group_name`` is what a worker uses to rebuild a branch, and it walks the tree that
``BranchSpec`` describes. Both are stable code that ``make_workflow`` relies on, which is why they stay in
``orchestrator.core.workflow`` while the beta parallel steps move to ``orchestrator.core.beta.parallel``.
"""

from __future__ import annotations

import pytest

from orchestrator.core.beta.parallel import map_parallel, parallel
from orchestrator.core.testing import WorkflowInstanceForTests
from orchestrator.core.workflow import (
    _find_step_by_group_name,
    begin,
    done,
    init,
    step,
    workflow,
)
from orchestrator.core.workflows import get_workflow


@step("Outer A")
def outer_a() -> dict:
    return {"outer_a": "done"}


@step("Outer B")
def outer_b() -> dict:
    return {"outer_b": "done"}


@step("Inner X")
def inner_x() -> dict:
    return {"inner_x": "done"}


@step("Inner Y")
def inner_y() -> dict:
    return {"inner_y": "done"}


@step("Mid M")
def mid_m() -> dict:
    return {"mid_m": "done"}


@step("Top C")
def top_c() -> dict:
    return {"top_c": "done"}


@step("Deep P")
def deep_p() -> dict:
    return {"deep_p": "done"}


@step("Deep Q")
def deep_q() -> dict:
    return {"deep_q": "done"}


def _make_find_wf(name: str):
    """Factory for workflow definitions used by _find_step_by_group_name tests."""
    match name:
        case "flat":

            @workflow()
            def flat_wf():
                return init >> parallel("TopLevel", begin >> outer_a, begin >> outer_b) >> done

            return flat_wf, "flat_wf"
        case "nested_parallel":

            @workflow()
            def nested_wf():
                return (
                    init
                    >> parallel(
                        "Outer",
                        begin >> outer_a >> parallel("Inner", begin >> inner_x, begin >> inner_y),
                        begin >> outer_b,
                    )
                    >> done
                )

            return nested_wf, "nested_find_wf"
        case "nested_map_parallel":

            @workflow()
            def fe_nested_wf():
                return (
                    init
                    >> map_parallel(
                        "FEOuter",
                        "items",
                        begin >> parallel("InsideFE", begin >> inner_x, begin >> inner_y),
                    )
                    >> done
                )

            return fe_nested_wf, "fe_nested_find_wf"
        case "three_levels":

            @workflow()
            def deep_wf():
                return (
                    init
                    >> parallel(
                        "L1",
                        begin
                        >> parallel("L2", begin >> parallel("L3", begin >> deep_p, begin >> deep_q), begin >> mid_m),
                        begin >> top_c,
                    )
                    >> done
                )

            return deep_wf, "deep_find_wf"
        case _:
            raise ValueError(f"Unknown workflow: {name}")


@pytest.mark.workflow
@pytest.mark.parametrize(
    ("wf_key", "search_name", "expected_found"),
    [
        pytest.param("flat", "TopLevel", True, id="top-level"),
        pytest.param("nested_parallel", "Inner", True, id="nested-in-parallel-branch"),
        pytest.param("nested_map_parallel", "InsideFE", True, id="nested-in-map_parallel-template"),
        pytest.param("three_levels", "L1", True, id="3-levels-L1"),
        pytest.param("three_levels", "L2", True, id="3-levels-L2"),
        pytest.param("three_levels", "L3", True, id="3-levels-L3"),
        pytest.param("flat", "DoesNotExist", False, id="missing-returns-none"),
    ],
)
def test_find_step_by_group_name(wf_key: str, search_name: str, expected_found: bool) -> None:
    """_find_step_by_group_name finds (or not) a parallel step at various nesting depths."""
    wf_func, wf_name = _make_find_wf(wf_key)

    with WorkflowInstanceForTests(wf_func, wf_name):
        wf = get_workflow(wf_name)
        assert wf is not None
        result = _find_step_by_group_name(wf.steps, search_name)

        if expected_found:
            assert result is not None, f"Expected to find '{search_name}' but got None"
            assert result.branching is not None
            assert result.branching.name == search_name
        else:
            assert result is None, f"Expected None for '{search_name}' but found a step"

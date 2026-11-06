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

from types import SimpleNamespace
from uuid import uuid4

import pytest

from orchestrator.core.utils.enrich_process import enrich_step_details
from orchestrator.core.workflow import BranchKind


def _step(branch_kind: str | None, branch_count: int | None = None, children: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        name="step",
        completed_at=SimpleNamespace(timestamp=lambda: 1.0),
        started_at=SimpleNamespace(timestamp=lambda: 0.0),
        importance="default",
        status="success",
        state={},
        created_by=None,
        step_id=uuid4(),
        branch_count=branch_count,
        branch_kind=branch_kind,
        branches_completed=branch_count or 0,
        child_steps=children or [],
    )


@pytest.mark.parametrize(
    "branch_kind,include_child_steps,expect_child_steps",
    [
        (BranchKind.PARALLEL, True, True),
        (BranchKind.MAP_PARALLEL, True, True),
        (BranchKind.PARALLEL, False, False),
        (None, True, False),
    ],
)
def test_enrich_step_details_gates_child_steps_on_branch_kind(branch_kind, include_child_steps, expect_child_steps):
    step = _step(branch_kind, branch_count=1, children=[_step(None)])

    result = enrich_step_details(step, None, include_child_steps=include_child_steps)

    assert result["branch_kind"] == branch_kind
    assert ("child_steps" in result) is expect_child_steps


def test_enrich_step_details_ignores_branch_count_without_branch_kind():
    result = enrich_step_details(_step(None, branch_count=2, children=[_step(None)]), None)

    assert "child_steps" not in result

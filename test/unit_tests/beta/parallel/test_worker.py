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

"""Unit tests for the Celery worker executor of the beta parallel steps.

The dispatch test lives here rather than with the branching helpers because it covers the parent side of the worker
executor, mirroring how ``test_threadpool.py`` covers the parent side of the thread pool executor.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.core.beta.parallel.worker import _dispatch_worker_branches
from orchestrator.core.workflow import StepList, Waiting, step


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


# -- executor dispatch --


@pytest.mark.parametrize("is_task", [pytest.param(True, id="task"), pytest.param(False, id="workflow")])
@patch("orchestrator.core.beta.parallel.worker._succeeded_branch_indices", return_value=set())
@patch("orchestrator.core.services.tasks.get_celery_task")
def test_worker_branches_submits_tasks_and_returns_waiting(
    mock_get_task: MagicMock, _mock_succeeded: MagicMock, is_task: bool
) -> None:
    # given
    mock_task = MagicMock()
    mock_get_task.return_value = mock_task

    fork_id = uuid4()
    process_id = uuid4()

    # when
    result = _dispatch_worker_branches(
        branches=[StepList([_step_a]), StepList([_step_b])],
        initial_state={"x": 1},
        process_id=process_id,
        current_user="test_user",
        fork_step_id=fork_id,
        is_task=is_task,
    )

    # then
    assert isinstance(result, Waiting)
    assert result.unwrap()["__parallel_waiting"] is True
    assert result.unwrap()["__fork_step_id"] == str(fork_id)
    assert mock_task.delay.call_count == 2

    # Verify correct task name was requested
    from orchestrator.core.services.tasks import (
        EXECUTE_PARALLEL_BRANCH_TASK,
        EXECUTE_PARALLEL_BRANCH_WORKFLOW,
    )

    expected_task = EXECUTE_PARALLEL_BRANCH_TASK if is_task else EXECUTE_PARALLEL_BRANCH_WORKFLOW
    mock_get_task.assert_called_once_with(expected_task)
